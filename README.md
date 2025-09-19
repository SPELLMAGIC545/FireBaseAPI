# User Score Tap API

## 概要

このプロジェクトは、ユーザーからの「タップ」を受け付け、それに対応するスコアをGoogle Firestoreから取得するためのシンプルなWeb APIサーバーです。タップ処理にはクールダウン機能が実装されており、連打を防ぎます。

UIDは一時的にサーバー内のSQLiteデータベースに保存され、スコア取得時に利用されます。

## ✨ 主な機能

-   **タップ処理**: `POST /tap` エンドポイントでUIDを受け取り、一時保存/削除を切り替えます。
-   **クールダウン**: 一度のタップ後、5秒間は次のタップを受け付けません（`429 Too Many Requests`を返却）。
-   **スコア取得**: `GET /score` エンドポイントで、一時保存されているUIDに対応するスコアをFirestoreから取得します。
-   **ユーザー情報取得**: `GET /users/...` エンドポイントでFirestore上のユーザーデータを確認できます。

## 🔧 セットアップ方法

#### 1. 前提条件

-   Python 3.8以上
-   Google Cloud PlatformプロジェクトおよびFirebaseプロジェクトが作成済みであること

#### 2. リポジトリのクローン

```bash
git clone <your-repository-url>
cd <your-repository-directory>
```

#### 3. 必要なライブラリのインストール

`requirements.txt` を使用して、必要なPythonライブラリをインストールします。

```bash
pip install -r requirements.txt
```

#### 4. Firebase認証キーの準備

1.  Firebaseコンソールから **サービスアカウント** の秘密鍵を生成します。
2.  ダウンロードしたJSONファイルを `serviceAccountKey.json` という名前に変更します。
3.  プロジェクトのルートディレクトリ（`api.py`と同じ階層）に配置してください。

#### 5. Firestoreデータベースの準備

1.  Firestoreデータベースを有効化してください。
2.  **`user_scores`** という名前でコレクションを作成します。
3.  `user_scores` コレクション内に、以下のような構造でドキュメントをいくつか作成しておきます。

    -   コレクション: `user_scores`
        -   ドキュメントID: (自動生成ID)
            -   `uid` (string): "user-abc-123"
            -   `score` (number): 100
        -   ドキュメントID: (自動生成ID)
            -   `uid` (string): "user-def-456"
            -   `score` (number): 50

## ▶️ 実行方法

以下のコマンドでAPIサーバーを起動します。

```bash
python api.py
```

サーバーが起動すると、ターミナルに以下のように表示されます。

```
INFO:     Uvicorn running on [http://0.0.0.0:8000](http://0.0.0.0:8000) (Press CTRL+C to quit)
✅ Firebase Admin SDKの初期化に成功しました。
```

ブラウザで `http://127.0.0.1:8000/docs` にアクセスすると、APIのドキュメント（Swagger UI）が表示され、各エンドポイントを直接テストできます。

## 📂 ディレクトリ構成

プロジェクトは以下のファイル構成を想定しています。

```
.
├── api.py                   # メインのAPIコード
├── requirements.txt         # 依存ライブラリ一覧
├── serviceAccountKey.json   # Firebase認証キー (Git管理外にすること)
└── temp_uid.db              # (初回実行時に自動生成) UIDを一時保存するDB
```

**注意**: `serviceAccountKey.json` は機密情報です。Gitなどのバージョン管理システムに含めないように、`.gitignore` ファイルに追記することを強く推奨します。
