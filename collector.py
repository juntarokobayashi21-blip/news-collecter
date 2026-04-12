import feedparser
import requests
import os
import webbrowser
from datetime import datetime
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

SOURCES = {
    "Hacker News": "https://news.ycombinator.com/rss",
    "Zenn": "https://zenn.dev/feed",
    "Qiita": "https://qiita.com/popular-items/feed",
    "Google News (IT)": "https://news.google.com/rss/search?q=technology&hl=ja&gl=JP&ceid=JP:ja",
    "Google News (Business)": "https://news.google.com/rss/search?q=business&hl=ja&gl=JP&ceid=JP:ja",
    "Reddit / technology": "https://www.reddit.com/r/technology/.rss",
    "Reddit / business": "https://www.reddit.com/r/business/.rss",
}

ITEMS_PER_SOURCE = 10

HEADERS = {
    "User-Agent": "news-collector/1.0"
}


def fetch_feed(name, url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        entries = feed.entries[:ITEMS_PER_SOURCE]
        return entries
    except Exception as e:
        print(f"  [エラー] {name}: {e}")
        return []


def format_output(results):
    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    lines.append("=" * 60)
    lines.append(f"  トレンドニュース - {today}")
    lines.append("=" * 60)
    lines.append("")

    for name, entries in results.items():
        lines.append(f"【{name}】")
        if not entries:
            lines.append("  （取得できませんでした）")
        else:
            for i, entry in enumerate(entries, 1):
                title = entry.get("title", "（タイトルなし）").strip()
                link = entry.get("link", "").strip()
                lines.append(f"  {i}. {title}")
                if link:
                    lines.append(f"     {link}")
        lines.append("")

    return "\n".join(lines)


def format_html(results):
    today = datetime.now().strftime("%Y-%m-%d")
    sections = ""
    for name, entries in results.items():
        items_html = ""
        if not entries:
            items_html = "<p class='empty'>取得できませんでした</p>"
        else:
            for entry in entries:
                title = entry.get("title", "（タイトルなし）").strip()
                link = entry.get("link", "").strip()
                if link:
                    items_html += f'<li><a href="{link}" target="_blank">{title}</a></li>\n'
                else:
                    items_html += f"<li>{title}</li>\n"
        sections += f"""
        <section>
            <h2>{name}</h2>
            <ul>{items_html}</ul>
        </section>
        """

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>トレンドニュース - {today}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; color: #333; }}
    header {{ background: #1a1a2e; color: white; padding: 2rem; text-align: center; }}
    header h1 {{ font-size: 1.6rem; font-weight: 400; letter-spacing: 0.05em; }}
    header p {{ margin-top: 0.4rem; opacity: 0.6; font-size: 0.9rem; }}
    main {{ max-width: 860px; margin: 2rem auto; padding: 0 1rem; }}
    section {{ background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    h2 {{ font-size: 1rem; font-weight: 600; color: #1a1a2e; border-left: 3px solid #e08030; padding-left: 0.7rem; margin-bottom: 1rem; }}
    ul {{ list-style: none; }}
    li {{ padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; font-size: 0.92rem; }}
    li:last-child {{ border-bottom: none; }}
    a {{ color: #1a6fa8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .empty {{ color: #aaa; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <header>
    <h1>トレンドニュース</h1>
    <p>{today}</p>
  </header>
  <main>
    {sections}
  </main>
</body>
</html>"""


def save_output(text, html):
    today = datetime.now().strftime("%Y-%m-%d")
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    txt_path = os.path.join(output_dir, f"{today}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    html_path = os.path.join(output_dir, f"{today}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return txt_path, html_path


def summarize_with_gemini(results):
    if not GEMINI_API_KEY:
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    articles = []
    for name, entries in results.items():
        for entry in entries[:5]:
            title = entry.get("title", "").strip()
            if title:
                articles.append(f"[{name}] {title}")
    if not articles:
        return None
    articles_text = "\n".join(articles)
    prompt = (
        "あなたはIT・ビジネスニュースのキュレーターです。"
        "以下のニュース記事タイトル一覧から、今日の重要なトレンドを3〜5点に絞り、"
        "日本語で簡潔に要約してください。Discord通知用に1500文字以内でまとめてください。\n\n"
        f"{today}のニュース一覧:\n{articles_text}"
    )
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(
            url,
            json=payload,
            params={"key": GEMINI_API_KEY},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"  [Gemini要約エラー] {e}")
        return None


def send_discord_notify(results, summary=None):
    if not DISCORD_WEBHOOK_URL:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    total = sum(len(entries) for entries in results.values())
    header = f"**【トレンドニュース】{today}**　合計 {total} 件\n"
    if summary:
        message = header + "\n" + summary
    else:
        lines = [header, "今日のニュースをお届けします :newspaper:", ""]
        for name, entries in results.items():
            if entries:
                title = entries[0].get("title", "").strip()
                lines.append(f"▶ **{name}**（{len(entries)}件）")
                lines.append(f"　{title}")
        message = "\n".join(lines)
    try:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message},
            timeout=10,
        )
    except Exception as e:
        print(f"  [Discord通知エラー] {e}")


def main():
    print("ニュース収集を開始します...\n")
    results = {}
    for name, url in SOURCES.items():
        print(f"  取得中: {name}")
        results[name] = fetch_feed(name, url)

    print("\n出力を生成中...")
    text = format_output(results)
    html = format_html(results)
    txt_path, html_path = save_output(text, html)
    print(f"\n完了！")
    print(f"  テキスト: {txt_path}")
    print(f"  HTML:     {html_path}")
    print("\nClaudeで要約中...")
    summary = summarize_with_gemini(results)
    send_discord_notify(results, summary)
    if html_path and os.path.exists(html_path):
        webbrowser.open(f"file:///{html_path.replace(os.sep, '/')}")


if __name__ == "__main__":
    main()
