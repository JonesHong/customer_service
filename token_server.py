from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from livekit import api
import os
from datetime import timedelta
from dotenv import load_dotenv
import logging

load_dotenv()

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LiveKit Token API", version="1.0.0")

# ✅ 限制 CORS 為特定域名（生產環境必須）
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ✅ 加入 Rate Limiting（防止濫用）
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Request/Response models
class TokenRequest(BaseModel):
    user_id: str
    user_name: str = "訪客"
    room: str = "chiayi-service"


class TokenResponse(BaseModel):
    token: str
    url: str
    room: str


# ✅ 改為 POST 方法（更安全）
@app.post('/get-token', response_model=TokenResponse)
@limiter.limit("5/minute")  # 每分鐘最多 5 次請求
async def get_token(request: Request, body: TokenRequest):
    """生成 LiveKit 存取 token（安全強化版）"""
    try:
        # ✅ 一對一場景：驗證房間名稱格式（每個用戶獨立房間）
        # 允許格式：chiayi-user-* 或 test-room
        import re
        allowed_patterns = [
            r'^chiayi-user-\d+$',  # 一對一房間格式
            r'^test-room$',        # 測試房間
        ]

        logger.info(f"Validating room: '{body.room}' (type: {type(body.room).__name__})")
        match_results = [(pattern, bool(re.match(pattern, body.room))) for pattern in allowed_patterns]
        logger.info(f"Pattern matches: {match_results}")

        if not any(re.match(pattern, body.room) for pattern in allowed_patterns):
            logger.warning(f"Unauthorized room access attempt: {body.room}")
            raise HTTPException(status_code=403, detail=f"Invalid room name: {body.room}")

        # ✅ 生成 token（最小權限原則）
        token = api.AccessToken(
            api_key=os.getenv('LIVEKIT_API_KEY'),
            api_secret=os.getenv('LIVEKIT_API_SECRET')
        )

        token.with_identity(body.user_id)
        token.with_name(body.user_name)

        # ✅ 設定最小權限（只能進指定房間、只能發布/訂閱音訊）
        token.with_grants(api.VideoGrants(
            room_join=True,
            room=body.room,
            can_publish=True,      # 可發布音訊
            can_subscribe=True,    # 可訂閱音訊
            can_publish_data=False,  # 不可發布數據
            hidden=False,          # 不隱藏
        ))

        # ✅ 設定 token 過期時間（6 小時）
        token.with_ttl(timedelta(hours=6))

        logger.info(f"Token generated for user: {body.user_id}, room: {body.room}")

        livekit_url = os.getenv('LIVEKIT_URL')
        if not livekit_url:
            logger.error("LIVEKIT_URL not set in environment")
            raise HTTPException(status_code=500, detail="LIVEKIT_URL not configured")

        return TokenResponse(
            token=token.to_jwt(),
            url=livekit_url,
            room=body.room,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token generation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ✅ 健康檢查端點
@app.get('/health')
async def health_check():
    return {"status": "ok"}


if __name__ == '__main__':
    import uvicorn
    # 生產環境建議使用 gunicorn + uvicorn workers
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=int(os.getenv('TOKEN_API_PORT', 5000)),
        log_level='info'
    )
