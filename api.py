import os
import uvicorn
import sqlite3
import datetime
import time # 変更点1: timeモジュールをインポート
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import firebase_admin
from firebase_admin import credentials, firestore

# --- グローバル変数 ---
# 最終タップ時刻を記録 (UNIXタイムスタンプ)
last_tap_time = 0.0

# --- 定数定義 ---
DB_FILE = "temp_uid.db"
TAP_COOLDOWN_SECONDS = 5 # タップのクールダウン秒数

# --- SQLite3 データベースの初期化 ---
def initialize_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temp_uid (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

initialize_db()

# --- FastAPIアプリケーションのインスタンスを作成 ---
app = FastAPI(
    title="User Score API",
    description="An API to temporarily store a UID and retrieve the corresponding score from Firestore."
)

# --- Firebase Admin SDKの初期化 ---
try:
    script_dir = os.path.dirname(__file__)
    cred_path = os.path.join(script_dir, 'serviceAccountKey.json')
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDKの初期化に成功しました。")
except Exception as e:
    print(f"❌ Firebase Admin SDKの初期化に失敗しました: {e}")
    exit()

db = firestore.client()
users_collection = db.collection('user_scores')

# --- データモデルの定義 (Pydantic) ---
class UIDPayload(BaseModel):
    uid: str = Field(..., description="ユーザー固有のID", example="user-abc-123")

class ScoreResponse(BaseModel):
    score: int

# --- APIエンドポイントの定義 ---

# 変更点2: エンドポイントを /uid から /tap に変更
@app.post("/tap", summary="UIDをタップ処理（保存/削除）")
def handle_tap(payload: UIDPayload):
    """
    UIDを受け取り、タップ処理を行います。
    - 5秒間のクールダウンがあります。連続してタップはできません。
    - 同じUIDが既に保存されている場合、そのUIDを削除します。
    - 異なるUIDまたは何も保存されていない場合、新しいUIDを保存します。
    """
    global last_tap_time
    current_time = time.time()

    # 変更点3: クールダウン処理
    if current_time - last_tap_time < TAP_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {TAP_COOLDOWN_SECONDS} seconds."
        )

    new_uid = payload.uid
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT uid FROM temp_uid LIMIT 1")
        result = cursor.fetchone()
        existing_uid = result[0] if result else None
        
        if existing_uid == new_uid:
            cursor.execute("DELETE FROM temp_uid WHERE uid = ?", (new_uid,))
            message = f"UID '{new_uid}' was already saved and has now been deleted."
            status_code = status.HTTP_200_OK
            content = {"message": message}
        else:
            cursor.execute("DELETE FROM temp_uid")
            cursor.execute("INSERT INTO temp_uid (uid) VALUES (?)", (new_uid,))
            message = "New UID saved successfully"
            status_code = status.HTTP_201_CREATED
            content = {"message": message, "uid": new_uid}
            
        conn.commit()
        conn.close()
        
        # 正常に処理が完了した場合のみ、最終タップ時刻を更新
        last_tap_time = current_time
        
        return JSONResponse(status_code=status_code, content=content)

    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred with the local database: {e}"
        )

@app.get("/score", response_model=ScoreResponse, summary="保存されたUIDのスコアを取得")
def get_user_score_from_firestore():
    uid = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT uid FROM temp_uid LIMIT 1")
        result = cursor.fetchone()
        conn.close()

        if result is None or result[0] is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="No UID is currently saved. Please POST a UID to /tap first."
            )
        
        uid = result[0]

    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred reading from the local database: {e}"
        )

    try:
        query = users_collection.where(field_path='uid', op_string='==', value=uid).limit(1)
        docs = list(query.stream())

        if not docs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with uid '{uid}' not found in Firestore")
        
        user_data = docs[0].to_dict()
        score = user_data.get('score')

        if score is None:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"score not found for user with uid '{uid}'")

        return {"score": int(score)}

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred querying Firestore: {e}"
        )

@app.get("/users/uid/{uid}", summary="UIDで特定ユーザースコアを取得")
def get_user_by_uid(uid: str):
    try:
        query = users_collection.where(field_path='uid', op_string='==', value=uid).limit(1)
        docs = query.stream()
        
        for doc in docs:
            found_user = doc.to_dict()
            found_user["document_id"] = doc.id
            return found_user

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with uid '{uid}' not found")

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {e}"
        )

@app.get("/users/", summary="全ユーザースコアのリスト取得")
def get_all_users():
    try:
        users_list = []
        docs_stream = users_collection.stream()
        for doc in docs_stream:
            user_data = doc.to_dict()
            user_data['document_id'] = doc.id
            users_list.append(user_data)
        
        return users_list

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {e}"
        )

# --- Uvicornサーバーの実行 ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)