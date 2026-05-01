import requests
import os
import glob
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv('.env.local', override=True)

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
SUMMARIZE_API = os.environ.get("SUMMARIZE_API", "groq").lower()
GITHUB_PAGES_BASE = os.environ.get(
    "GITHUB_PAGES_BASE",
    "https://juntarokobayashi21-blip.github.io/news-collecter/output"
)

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


def collect_week_texts():
    """過去7日分の .txt ファイルを取得（存在しない日はスキップ）"""
    output_base = os.path.join(os.path.dirname(__file__), "output")
    week_texts = []

    # 実行日から過去7日を遡る
    today = datetime.now()
    for i in range(7, 0, -1):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        iso_year, iso_week, _ = date.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"
        txt_path = os.path.join(output_base, week_label, f"{date_str}.txt")
        if os.path.exists(txt_path):
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    week_texts.append((date_str, content))
                    print(f"  読込: {date_str}")
            except Exception as e:
                print(f"  [エラー] {date_str}: {e}")
        else:
            print(f"  スキップ: {date_str} (ファイルなし)")

    return week_texts


def summarize_week_with_groq(week_texts):
    """週間要約を生成（Groq API）"""
    if not GROQ_API_KEY or not week_texts:
        return None, "GROQ_API_KEY が設定されていません" if not GROQ_API_KEY else "要約対象の記事がありません"

    # 週のテキストを結合（日付をヘッダーに）
    combined = ""
    for date_str, text in week_texts:
        combined += f"\n\n===== {date_str} =====\n{text}"

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "あなたはIT・ビジネスニュースのキュレーターです。過去1週間のニュース記事一覧から、この週の重要なトレンドを日本語で簡潔にまとめてください。Discord通知用に1500文字以内でまとめてください。",
                    },
                    {
                        "role": "user",
                        "content": f"過去1週間のニュース記事です。この週の重要なトレンドを3〜5点に絞って簡潔に要約してください。\n{combined}",
                    },
                ],
                "max_tokens": 1024,
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


def summarize_week_with_claude(week_texts):
    """週間要約を生成（Claude API）"""
    if not CLAUDE_API_KEY or not week_texts:
        return None, "CLAUDE_API_KEY が設定されていません" if not CLAUDE_API_KEY else "要約対象の記事がありません"

    from anthropic import Anthropic

    # 週のテキストを結合（日付をヘッダーに）
    combined = ""
    for date_str, text in week_texts:
        combined += f"\n\n===== {date_str} =====\n{text}"

    try:
        client = Anthropic(api_key=CLAUDE_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"あなたはIT・ビジネスニュースのキュレーターです。以下の過去1週間のニュース記事から、この週の重要なトレンドを日本語で簡潔にまとめてください。Discord通知用に1500文字以内でまとめてください。重要なトレンドを3〜5点に絞って簡潔に要約してください。\n{combined}",
                }
            ],
        )
        summary = message.content[0].text
        return summary, None
    except Exception as e:
        error_msg = f"Claude API エラー: {str(e)}"
        print(f"  [{error_msg}]")
        return None, error_msg


def summarize_week(week_texts):
    """API選択に基づいて週間要約を生成"""
    if SUMMARIZE_API == "claude":
        return summarize_week_with_claude(week_texts)
    else:
        return summarize_week_with_groq(week_texts)


def get_week_label():
    """週番号をラベルに変換（ISO形式）"""
    today = datetime.now()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def format_weekly_html(week_texts, summary=None):
    """週間まとめのHTMLを生成"""
    week_label = get_week_label()

    # 日付カードをグリッド生成
    daily_cards = ""
    for date_str, text in week_texts:
        article_count = len([line for line in text.split('\n') if line.strip() and not line.startswith('=') and not line.startswith('【')])
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        iso_year, iso_week, _ = date_obj.isocalendar()
        date_week_label = f"{iso_year}-W{iso_week:02d}"
        daily_cards += f'''
        <div class="daily-card">
            <h3>{date_str}</h3>
            <p class="article-count">{article_count} 件</p>
            <a href="{GITHUB_PAGES_BASE}/{date_week_label}/{date_str}.html" class="view-link">詳細レポート →</a>
        </div>'''

    overall_html = ""
    if summary:
        overall_html = f'''
        <section class="hero">
            <h2>📰 今週のトレンド要約</h2>
            <div class="overall-summary">{parse_simple_markdown(summary)}</div>
        </section>'''

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>週間トレンドニュース - {week_label}</title>
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

        section h2 {{
            font-size: 1.4rem;
            margin-bottom: 1.5rem;
            color: var(--accent);
        }}

        section h3 {{
            font-size: 1.1rem;
            margin-top: 1rem;
            margin-bottom: 0.8rem;
            color: var(--text);
            font-weight: 600;
        }}

        .hero {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin-bottom: 2.5rem;
        }}

        .hero h2 {{
            font-size: 1.8rem;
            color: white;
        }}

        .overall-summary {{
            background: rgba(255,255,255,0.1);
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 1rem;
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

        .daily-grid {{
            background: var(--card);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        .daily-grid h2 {{
            margin-bottom: 1.5rem;
            color: var(--accent);
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1.2rem;
        }}

        @media (max-width: 768px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .daily-card {{
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
        }}

        .daily-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.12);
            border-color: var(--accent);
        }}

        .daily-card h3 {{
            margin: 0;
            color: var(--accent);
            font-size: 1.2rem;
        }}

        .article-count {{
            margin: 0;
            font-size: 0.9rem;
            opacity: 0.7;
        }}

        .view-link {{
            color: var(--accent);
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s ease;
            margin-top: auto;
        }}

        .view-link:hover {{
            color: var(--success);
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
        <h1>📰 週間トレンドニュース</h1>
        <p>{week_label}</p>
    </header>

    <main>
        {overall_html}
        <section class="daily-grid">
            <h2>毎日のニュース</h2>
            <div class="grid">
                {daily_cards}
            </div>
        </section>
    </main>

    <footer>
        <p>生成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | API: {SUMMARIZE_API.upper()}</p>
    </footer>
</body>
</html>"""


def save_weekly_output(html):
    """週間HTMLを保存"""
    week_label = get_week_label()
    output_dir = os.path.join(os.path.dirname(__file__), "output", week_label)
    os.makedirs(output_dir, exist_ok=True)

    html_path = os.path.join(output_dir, f"weekly-{week_label}.html")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return html_path


def send_discord_notify(summary=None):
    """Discord に週間まとめを通知"""
    if not DISCORD_WEBHOOK_URL:
        return

    week_label = get_week_label()
    url = f"{GITHUB_PAGES_BASE}/{week_label}/weekly-{week_label}.html"
    header = f"**【週間トレンドニュース】{week_label}**\n{url}\n"

    if summary:
        message = header + "\n" + summary
    else:
        message = header + "今週のニュースをお届けします :newspaper:"

    try:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message},
            timeout=10,
        )
        print("  Discord 通知を送信しました")
    except Exception as e:
        print(f"  [Discord通知エラー] {e}")


def main():
    print("週間ニュースまとめを生成します...\n")

    print("過去7日分のニュースを読み込み中...")
    week_texts = collect_week_texts()

    if not week_texts:
        print("取得可能なニュースファイルがありません")
        return

    print(f"\n週間まとめを生成中（{len(week_texts)}日分）...")
    summary, summary_error = summarize_week(week_texts)

    if summary_error:
        print(f"  ⚠️ {summary_error}")
    if summary:
        print("  要約を生成しました")

    print("\n週間 HTML を生成中...")
    html = format_weekly_html(week_texts, summary)
    html_path = save_weekly_output(html)
    print(f"  保存: {html_path}")

    print("\nDiscord 通知を送信中...")
    send_discord_notify(summary)

    print("\n完了！")


if __name__ == "__main__":
    main()
