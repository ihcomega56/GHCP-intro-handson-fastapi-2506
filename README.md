# Chaos Kakeibo (カオス家計簿)

家計簿データを管理・集計するためのRESTful APIを提供するFastAPIアプリケーション。

## 技術スタック
- Python 3.12.x
- FastAPI 0.115.x
- Uvicorn 0.34.x

## ローカル環境での実行手順

### Python環境のセットアップ

#### Windows

1. [Python公式サイト](https://www.python.org/downloads/)から最新バージョン（3.12以上推奨）をダウンロード
2. インストーラを起動し **★ 必ず `Add Python to PATH` にチェック** → **Install Now**
3. インストール完了後、コマンドプロンプトかPowerShellを開き、以下のコマンドでPython 3.12.x がインストールされたことを確認
   ```
   python --version
   ```

> **注意**: Windowsでは通常 `python` コマンドでPython 3系が実行されます。これは一般的にWindowsにはPython 2系が標準でインストールされていないためです。

#### macOS

```bash
# Homebrewがインストールされていない場合
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Pythonのインストール
brew install python@3.12

# 確認
python3 --version   # → Python 3.12.x
```

> **注意**: macOSやLinuxでは、`python` コマンドがPython 2系を、`python3` コマンドがPython 3系を指す場合があります。そのため、これらの環境では明示的に `python3` コマンドを使用することをお勧めします。

### アプリケーションの実行

#### ローカルで仮想環境を立ち上げる場合

```bash
# 仮想環境の作成と有効化
# macOSとLinuxの場合
python3 -m venv venv
source venv/bin/activate  # 仮想環境に入ると、プロンプト前に (venv) が付きます

# Windowsの場合
python -m venv venv
.\venv\Scripts\activate   # 仮想環境に入ると、プロンプト前に (venv) が付きます

# 依存関係のインストール
pip install -r requirements.txt

# アプリケーションの起動
uvicorn app.main:app --reload --port 8000

# サンプルデータの追加
# ブラウザで http://localhost:8000/sample にアクセス
# または curl http://localhost:8000/sample
```

#### Dev Containerを使用する場合

- VS Codeで開発フォルダを開く
- コマンドパレット（**View > Command Palette...**）を開き、**Dev Container: Reopen in Container**を実行
- コンテナビルドが完了すると、必要な依存関係が自動的にインストールされます
- Run and Debugビューやターミナルで`uvicorn app.main:app --reload --port 8000`を実行

## 動作確認用curlコマンド

サーバー起動後、以下のコマンドでAPIの動作確認ができます。
**注意**: 演習用に複数のエンドポイントが同じURLパスに登録されているため、一部の操作が競合して正しく動作しない場合があります。これはあえて「リファクタリングすべき問題」として残されています。

### ヘルスチェック
```bash
curl http://localhost:8000/healthz
```

### サンプルデータの追加
```bash
curl -X POST http://localhost:8000/sample
```

### レシート登録（JSONデータ）
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '[{"date": "2023-04-01", "category": "食費", "description": "スーパー", "amount": "2500"}]'
```

### データ一覧取得
```bash
curl http://localhost:8000/
```

### 日付でフィルタリング
```bash
curl "http://localhost:8000/?date_from=2023-01-01&date_to=2023-01-31"
```

### カテゴリでフィルタリング
```bash
curl "http://localhost:8000/?category=食費"
```

### 月次サマリー取得
```bash
curl "http://localhost:8000/?year_month=2023-01"
```

### CSVエクスポート
```bash
curl -o export.csv http://localhost:8000/export
```

### データの全削除
```bash
curl -X POST "http://localhost:8000/clear_data?confirm=true"
```

## APIドキュメント
サーバー起動後、以下のURLにアクセスしてSwagger UIによるAPIドキュメントを確認できます：
http://localhost:8000/docs