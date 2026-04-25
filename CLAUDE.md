# CLAUDE.md

このファイルは Claude Code (claude.ai/code) がこのリポジトリで作業するときの指針を提供します。

## プロジェクト概要

**news-collector** は、複数の RSS フィードから IT・ビジネスニュースを自動収集し、Groq の Llama API で要約して、毎日 Discord に配信するシステムです。生成された HTML とテキストファイルは GitHub Pages で公開されます。

## スクリプト実行

**ローカル実行：**
```bash
python collector.py
```

**ローカル開発環境のセットアップ：**
```bash
pip install -r requirements.txt
```

**環境変数の設定：**

ローカルテスト時は `.env.local` ファイルを作成して環境変数を設定します：

```bash
cp .env.example .env.local
# .env.local を編集して、実際の値を入力
```

`.env.local` の内容例：
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
GROQ_API_KEY=gsk_...
```

- `DISCORD_WEBHOOK_URL` – Discord webhook (省略可；ない場合は通知をスキップ)
- `GROQ_API_KEY` – Groq API キー (省略可；ない場合は要約をスキップ)

**注：** `.env.local` は `.gitignore` で除外されるため、ローカル環境専用です。GitHub Actions は GitHub Secrets から環境変数を読み込みます。

## アーキテクチャ

### 単一モジュール設計
`collector.py` で全処理を実行：

1. **フィード取得** (`fetch_feed`)
   - 7つのソース (Hacker News、Zenn、Qiita、Google News ×2、Reddit ×2) から RSS 取得
   - ソースあたり上位 10 件を抽出
   - 取得失敗したソースはスキップ

2. **出力フォーマット** (`format_output`、`format_html`)
   - テキスト版：ソース別グループ化の平文リスト
   - HTML 版：CSS 埋め込みのスタイル付きレポート

3. **要約** (`summarize_with_groq`)
   - ソースあたり上位 5 件を入力
   - 日本語プロンプト (IT・ビジネストレンド重視) で Groq API を呼び出し
   - 最大 1500 文字
   - API キーなければスキップ

4. **Discord 通知** (`send_discord_notify`)
   - 要約（または要約なしの場合は各ソース最新記事）をポスト
   - GitHub Pages 公開 HTML へのリンクを含む
   - webhook URL なければスキップ

5. **ファイル保存** (`save_output`)
   - `output/YYYY-MM-DD.{txt,html}` に保存
   - output ディレクトリを自動作成

### データフロー
```
RSS フィード (7 URL) 取得 → パース
            ↓
            テキスト + HTML フォーマット
            ↓
            output/YYYY-MM-DD.{txt,html} に保存
            ↓
            要約 (Groq) + Discord 通知
            ↓
            HTML をブラウザで開く (ローカルのみ)
```

## 毎日の自動実行

GitHub Actions ワークフロー (`.github/workflows/daily-news.yml`)：
- **スケジュール：** 毎日 23:00 UTC (= 翌朝 08:00 JST)
- **手動実行：** workflow_dispatch で可能
- **処理流程：** 依存をインストール → collector.py 実行 → output/ をコミット → プッシュ
- **シークレット：** DISCORD_WEBHOOK_URL、GROQ_API_KEY を環境変数として渡す

## 設定

**RSS フィードソース** は collector.py 内の `SOURCES` 辞書にハードコーディングされています。追加・削除・変更する場合はここを編集します。

**記事数上限：** `ITEMS_PER_SOURCE = 10` でソースあたりの取得件数を制御します。

**User-Agent：** requests ヘッダーに "news-collector/1.0" が固定。

## シークレット・権限

- **Claude Code 権限** (`.claude/settings.local.json`）：gist.github.com、b.hatena.ne.jp、news.ycombinator.com、zenn.dev、qiita.com、news.google.com、discord.com での WebFetch を許可
- **GitHub Actions シークレット：** リポジトリ設定で DISCORD_WEBHOOK_URL、GROQ_API_KEY を登録
- **Groq モデル：** `llama-3.3-70b-versatile` (API リクエストにハードコーディング)
- **Discord メッセージフォーマット：** カスタムフォーマット；要約優先、要約がない場合は各ソース最新記事

## よくある変更

- **新しい RSS ソースを追加：** `SOURCES` 辞書に名前と URL を追加
- **記事数を変更：** `ITEMS_PER_SOURCE` または `summarize_with_groq` 内の `[:5]` を変更
- **出力形式を変更：** `format_output` と `format_html` 関数を編集
- **通知の動作を変更：** `send_discord_notify` またはメッセージテンプレートを編集
- **要約モデルを切り替え：** `summarize_with_groq` 内の Groq API コールの `model` フィールドを更新
