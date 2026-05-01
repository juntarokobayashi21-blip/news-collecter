import feedparser
import requests
import os
import webbrowser
import time
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv('.env.local', override=True)

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
SUMMARIZE_API = os.environ.get("SUMMARIZE_API", "groq").lower()
GITHUB_PAGES_BASE = os.environ.get(
    "GITHUB_PAGES_BASE",
    "https://juntarokobayashi21-blip.github.io/news-collecter/output"
)

SOURCES = {
    "Hacker News": "https://news.ycombinator.com/rss",
    "Zenn": "https://zenn.dev/feed",
    "Qiita": "https://qiita.com/popular-items/feed",
    "Google News (IT)": "https://news.google.com/rss/search?q=technology&hl=ja&gl=JP&ceid=JP:ja",
    "Google News (Business)": "https://news.google.com/rss/search?q=business&hl=ja&gl=JP&ceid=JP:ja",
    "Reddit / technology": "https://www.reddit.com/r/technology/.rss",
    "Reddit / business": "https://www.reddit.com/r/business/.rss",
}

SOURCE_BADGES = {
    "Hacker News": ("Dev", "#ff6600", "🚀"),
    "Zenn": ("日本語Tech", "#3ea8ff", "📚"),
    "Qiita": ("日本語Tech", "#55c500", "✏️"),
    "Google News (IT)": ("ニュース", "#4285f4", "📰"),
    "Google News (Business)": ("ビジネス", "#0f9d58", "💼"),
    "Reddit / technology": ("Community", "#ff4500", "💬"),
    "Reddit / business": ("Community", "#ff4500", "💬"),
}

ITEMS_PER_SOURCE = 10

HEADERS = {
    "User-Agent": "news-collector/1.0"
}


def parse_simple_markdown(text):
    if not text:
        return text
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'##\s+(.+?)(?=\n|$)', r'<h4>\1</h4>', text)
    text = text.replace('\n', '<br>')
    return text


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


def format_html(results, source_summaries=None, article_summaries=None, overall_summary=None):
    today = datetime.now().strftime("%Y-%m-%d")
    if source_summaries is None:
        source_summaries = {}
    if article_summaries is None:
        article_summaries = {}
    sections = ""
    for name, entries in results.items():
        items_html = ""
        if not entries:
            items_html = "<p class='empty'>取得できませんでした</p>"
        else:
            article_idx = 0
            for entry in entries:
                title = entry.get("title", "（タイトルなし）").strip()
                link = entry.get("link", "").strip()
                article_summary = ""
                if name in article_summaries and article_idx < len(article_summaries[name]):
                    summary_text = article_summaries[name][article_idx]
                    if summary_text:
                        article_summary = f'<div class="article-summary">{summary_text}</div>\n'
                article_idx += 1
                if link:
                    items_html += f'<li><a href="{link}" target="_blank">{title}</a>\n{article_summary}</li>\n'
                else:
                    items_html += f"<li>{title}\n{article_summary}</li>\n"
        summary_html = ""
        if name in source_summaries and source_summaries[name]:
            summary_html = f'<div class="summary">{source_summaries[name]}</div>\n'
        sections += f"""
        <section>
            <h2>{name}</h2>
            {summary_html}<ul>{items_html}</ul>
        </section>
        """

    total_articles = sum(len(entries) for entries in results.values())
    nav_html = "".join(
        f'<a href="#{i}" class="nav-link">{name}</a>'
        for i, name in enumerate(results.keys())
    )

    sections_html = ""
    for i, (name, entries) in enumerate(results.items()):
        badge_name, badge_color, badge_icon = SOURCE_BADGES.get(name, ("その他", "#999", "📄"))
        article_cards = ""

        if entries:
            for j, entry in enumerate(entries):
                title = entry.get("title", "（タイトルなし）").strip()
                link = entry.get("link", "").strip()
                summary_text = ""
                if name in article_summaries and j < len(article_summaries[name]):
                    summary = article_summaries[name][j]
                    if summary:
                        summary_text = f'<p class="article-summary">{parse_simple_markdown(summary)}</p>'

                article_cards += f'''
                <a href="{link}" target="_blank" class="article-card">
                    <span class="article-title">{title}</span>
                    {summary_text}
                </a>'''

        section_summary = ""
        if name in source_summaries and source_summaries[name]:
            section_summary = f'<div class="section-summary">{parse_simple_markdown(source_summaries[name])}</div>'

        sections_html += f'''
        <section id="{i}">
            <div class="section-header">
                <h2>{name}</h2>
                <span class="badge" style="background-color: {badge_color};">{badge_icon} {badge_name}</span>
            </div>
            {section_summary}
            <div class="articles-grid">
                {article_cards}
            </div>
        </section>'''

    overall_html = ""
    if overall_summary:
        overall_html = f'''
        <section class="hero">
            <h2>📰 今日のトレンド要約</h2>
            <div class="overall-summary">{parse_simple_markdown(overall_summary)}</div>
            <div class="stats">
                <div class="stat"><strong>{len(results)}</strong> ソース</div>
                <div class="stat"><strong>{total_articles}</strong> 記事</div>
            </div>
        </section>'''

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>トレンドニュース - {today}</title>
    <style>
        :root {{
            --bg: #f8f9fa;
            --text: #1a1a2e;
            --card: white;
            --border: #e9ecef;
            --accent: #3b82f6;
            --success: #10b981;
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #1a1a2e;
                --text: #f0f0f0;
                --card: #2a2a3e;
                --border: #3a3a4e;
                --accent: #60a5fa;
                --success: #34d399;
            }}
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            transition: background-color 0.3s ease, color 0.3s ease;
        }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 3rem 1rem;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}

        header h1 {{
            font-size: 2.2rem;
            margin-bottom: 0.5rem;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}

        header p {{
            font-size: 1rem;
            opacity: 0.9;
        }}

        nav {{
            position: sticky;
            top: 0;
            background: var(--card);
            border-bottom: 1px solid var(--border);
            padding: 0.8rem 1rem;
            display: flex;
            gap: 1rem;
            overflow-x: auto;
            z-index: 100;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}

        .nav-link {{
            color: var(--text);
            text-decoration: none;
            font-size: 0.9rem;
            padding: 0.4rem 0.8rem;
            border-radius: 4px;
            white-space: nowrap;
            transition: background-color 0.2s ease;
        }}

        .nav-link:hover {{
            background-color: var(--accent);
            color: white;
        }}

        main {{
            max-width: 1000px;
            margin: 2rem auto;
            padding: 0 1rem;
        }}

        section {{
            background: var(--card);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: box-shadow 0.3s ease;
        }}

        section:hover {{
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        }}

        .hero {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin-bottom: 2.5rem;
        }}

        .hero h2 {{
            font-size: 1.8rem;
            margin-bottom: 1rem;
        }}

        .overall-summary {{
            background: rgba(255,255,255,0.1);
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            font-size: 1rem;
            line-height: 1.8;
        }}

        .overall-summary strong {{
            font-weight: 600;
        }}

        .overall-summary h4 {{
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            font-size: 1.1rem;
        }}

        .stats {{
            display: flex;
            gap: 2rem;
            justify-content: flex-start;
        }}

        .stat {{
            font-size: 0.95rem;
            opacity: 0.9;
        }}

        .stat strong {{
            font-size: 1.4rem;
            display: block;
            margin-bottom: 0.3rem;
        }}

        .section-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .section-header h2 {{
            font-size: 1.4rem;
            margin: 0;
            flex: 1;
        }}

        .badge {{
            display: inline-block;
            color: white;
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            white-space: nowrap;
        }}

        .section-summary {{
            background: var(--bg);
            padding: 1rem;
            border-left: 4px solid var(--accent);
            border-radius: 4px;
            margin-bottom: 1.5rem;
            font-size: 0.95rem;
            line-height: 1.7;
        }}

        .section-summary strong {{
            font-weight: 600;
        }}

        .section-summary h4 {{
            margin-top: 0.8rem;
            margin-bottom: 0.4rem;
            font-size: 1rem;
        }}

        .articles-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.2rem;
        }}

        @media (max-width: 768px) {{
            .articles-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .article-card {{
            display: block;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.2rem;
            transition: all 0.3s ease;
            cursor: pointer;
            text-decoration: none;
            color: inherit;
        }}

        .article-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.12);
            border-color: var(--accent);
        }}

        .article-title {{
            display: block;
            color: var(--accent);
            font-weight: 600;
            font-size: 1rem;
            line-height: 1.4;
            margin-bottom: 0.8rem;
            transition: color 0.2s ease;
        }}

        .article-card:hover .article-title {{
            color: var(--success);
            text-decoration: underline;
        }}

        .article-summary {{
            font-size: 0.9rem;
            color: var(--text);
            opacity: 0.85;
            line-height: 1.6;
            margin: 0;
        }}

        footer {{
            text-align: center;
            padding: 2rem 1rem;
            border-top: 1px solid var(--border);
            margin-top: 3rem;
            font-size: 0.85rem;
            opacity: 0.7;
        }}
    </style>
</head>
<body>
    <header>
        <h1>📊 トレンドニュース</h1>
        <p>{today}</p>
    </header>

    <nav>
        {nav_html}
    </nav>

    <main>
        {overall_html}
        {sections_html}
    </main>

    <footer>
        <p>生成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | API: {SUMMARIZE_API.upper()}</p>
    </footer>
</body>
</html>"""


def save_output(text, html, source_summaries=None, article_summaries=None):
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    iso_year, iso_week, _ = today.isocalendar()
    week_label = f"{iso_year}-W{iso_week:02d}"
    output_dir = os.path.join(os.path.dirname(__file__), "output", week_label)
    os.makedirs(output_dir, exist_ok=True)

    txt_path = os.path.join(output_dir, f"{date_str}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    html_path = os.path.join(output_dir, f"{date_str}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return txt_path, html_path


def summarize_article_with_groq(title, retry=3):
    if not GROQ_API_KEY or not title:
        return None
    for attempt in range(retry):
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {
                            "role": "system",
                            "content": "記事のタイトルを読んで、1行（最大100文字）で簡潔に内容を要約してください。重要なキーワードやフレーズは **太文字** で強調してください。",
                        },
                        {
                            "role": "user",
                            "content": title,
                        },
                    ],
                    "max_tokens": 150,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                print(f"  [記事要約エラー] 予期しないレスポンス形式: {data}")
                return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                if attempt < retry - 1:
                    wait_time = 2 ** attempt
                    print(f"    [レート制限] {wait_time}秒待機中...")
                    time.sleep(wait_time)
                else:
                    print(f"  [記事要約エラー] レート制限に達しました（リトライ回数超過）")
                    return None
            else:
                print(f"  [記事要約エラー] {type(e).__name__}: {e}")
                return None
        except Exception as e:
            print(f"  [記事要約エラー] {type(e).__name__}: {e}")
            return None


def summarize_article_with_claude(title):
    if not CLAUDE_API_KEY or not title:
        return None
    try:
        client = Anthropic(api_key=CLAUDE_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[
                {
                    "role": "user",
                    "content": f"記事のタイトルを読んで、1行（最大100文字）で簡潔に内容を要約してください。重要なキーワードやフレーズは **太文字** で強調してください。\n\n{title}",
                }
            ],
        )
        return message.content[0].text
    except Exception as e:
        print(f"  [記事要約エラー] {type(e).__name__}: {e}")
        return None


def summarize_article(title):
    if SUMMARIZE_API == "claude":
        return summarize_article_with_claude(title)
    else:
        return summarize_article_with_groq(title)


def summarize_source_with_groq(source_name, entries):
    if not GROQ_API_KEY or not entries:
        return None
    articles = []
    for entry in entries[:5]:
        title = entry.get("title", "").strip()
        if title:
            articles.append(title)
    if not articles:
        return None
    articles_text = "\n".join(articles)
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "与えられたニュース記事のタイトル一覧から、2〜3行で簡潔に要約してください。重要なキーワードやフレーズは **太文字** で強調してください。",
                    },
                    {
                        "role": "user",
                        "content": f"「{source_name}」のニュース記事です。簡潔に要約してください。\n\n{articles_text}",
                    },
                ],
                "max_tokens": 400,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  [{source_name} 要約エラー] {e}")
        return None


def summarize_source_with_claude(source_name, entries):
    if not CLAUDE_API_KEY or not entries:
        return None
    articles = []
    for entry in entries[:5]:
        title = entry.get("title", "").strip()
        if title:
            articles.append(title)
    if not articles:
        return None
    articles_text = "\n".join(articles)
    try:
        client = Anthropic(api_key=CLAUDE_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[
                {
                    "role": "user",
                    "content": f"「{source_name}」のニュース記事です。与えられたタイトル一覧から、2〜3行で簡潔に要約してください。重要なキーワードやフレーズは **太文字** で強調してください。\n\n{articles_text}",
                }
            ],
        )
        return message.content[0].text
    except Exception as e:
        print(f"  [{source_name} 要約エラー] {e}")
        return None


def summarize_source(source_name, entries):
    if SUMMARIZE_API == "claude":
        return summarize_source_with_claude(source_name, entries)
    else:
        return summarize_source_with_groq(source_name, entries)


def summarize_overall_with_groq(results):
    if not GROQ_API_KEY:
        return None, "GROQ_API_KEY が設定されていません"
    today = datetime.now().strftime("%Y-%m-%d")
    articles = []
    for name, entries in results.items():
        for entry in entries[:5]:
            title = entry.get("title", "").strip()
            if title:
                articles.append(f"[{name}] {title}")
    if not articles:
        return None, "要約対象の記事がありません"
    articles_text = "\n".join(articles)
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "あなたはIT・ビジネスニュースのキュレーターです。収集したニュース記事のタイトル一覧から、今日の重要なトレンドを日本語で簡潔にまとめてください。Discord通知用に1500文字以内でまとめてください。重要なキーワードやフレーズは **太文字** で強調してください。",
                    },
                    {
                        "role": "user",
                        "content": f"{today}のニュース記事一覧です。重要なトレンドを3〜5点に絞って簡潔に要約してください。\n\n{articles_text}",
                    },
                ],
                "max_tokens": 1500,
            },
            timeout=30,
        )
        response.raise_for_status()
        summary = response.json()["choices"][0]["message"]["content"]
        return summary, None
    except Exception as e:
        error_msg = f"Groq API エラー: {str(e)}"
        print(f"  [{error_msg}]")
        return None, error_msg


def summarize_overall_with_claude(results):
    if not CLAUDE_API_KEY:
        return None, "CLAUDE_API_KEY が設定されていません"
    today = datetime.now().strftime("%Y-%m-%d")
    articles = []
    for name, entries in results.items():
        for entry in entries[:5]:
            title = entry.get("title", "").strip()
            if title:
                articles.append(f"[{name}] {title}")
    if not articles:
        return None, "要約対象の記事がありません"
    articles_text = "\n".join(articles)
    try:
        client = Anthropic(api_key=CLAUDE_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": f"あなたはIT・ビジネスニュースのキュレーターです。以下の記事タイトルから、{today}の重要なトレンドを日本語で簡潔にまとめてください。Discord通知用に1500文字以内でまとめてください。重要なトレンドを3〜5点に絞って簡潔に要約してください。重要なキーワードやフレーズは **太文字** で強調してください。\n\n{articles_text}",
                }
            ],
        )
        summary = message.content[0].text
        return summary, None
    except Exception as e:
        error_msg = f"Claude API エラー: {str(e)}"
        print(f"  [{error_msg}]")
        return None, error_msg


def summarize_overall(results):
    if SUMMARIZE_API == "claude":
        return summarize_overall_with_claude(results)
    else:
        return summarize_overall_with_groq(results)


def send_discord_notify(results, summary=None, summary_error=None):
    if not DISCORD_WEBHOOK_URL:
        return
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    iso_year, iso_week, _ = today.isocalendar()
    week_label = f"{iso_year}-W{iso_week:02d}"
    total = sum(len(entries) for entries in results.values())
    url = f"{GITHUB_PAGES_BASE}/{week_label}/{date_str}.html"
    header = f"**【トレンドニュース】{date_str}**　合計 {total} 件\n{url}\n"
    if summary:
        message = header + "\n" + summary
    else:
        lines = [header, "今日のニュースをお届けします :newspaper:", ""]
        for name, entries in results.items():
            if entries:
                title = entries[0].get("title", "").strip()
                lines.append(f"▶ **{name}**（{len(entries)}件）")
                lines.append(f"　{title}")
        if summary_error:
            lines.append("")
            lines.append(f"⚠️ {summary_error}")
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

    print("\n各記事の要約を生成中...")
    article_summaries = {}
    for name, entries in results.items():
        if entries:
            print(f"  {name} ({len(entries)} 件)")
            article_summaries[name] = []
            for entry in entries:
                title = entry.get("title", "").strip()
                if title:
                    summary = summarize_article(title)
                    article_summaries[name].append(summary)
                else:
                    article_summaries[name].append(None)
                time.sleep(2)

    print("\n全体の要約を生成中...")
    summary, summary_error = summarize_overall(results)

    print("\nセクション要約を生成中...")
    source_summaries = {}
    for name, entries in results.items():
        if entries:
            source_summaries[name] = summarize_source(name, entries)
            time.sleep(2)

    print("\n出力を生成中...")
    text = format_output(results)
    html = format_html(results, source_summaries, article_summaries, summary)
    txt_path, html_path = save_output(text, html, source_summaries, article_summaries)
    print(f"\n完了！")
    print(f"  テキスト: {txt_path}")
    print(f"  HTML:     {html_path}")
    send_discord_notify(results, summary, summary_error)
    if html_path and os.path.exists(html_path):
        webbrowser.open(f"file:///{html_path.replace(os.sep, '/')}")


if __name__ == "__main__":
    main()
