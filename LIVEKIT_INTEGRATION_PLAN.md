# LiveKit 語音整合計畫書（針對現有 Next.js 前端）- 專家審核修正版

> **重要提醒**：本計畫書已根據 LiveKit 專家審核意見修正，包含回音消除、自動播放策略、安全性強化等關鍵改進。

## 專案概述

將嘉義客服聊天機器人系統整合 LiveKit 即時語音功能，在現有的 Next.js + Spline 3D 前端基礎上加入語音互動能力。

**使用場景**：一對一客服對話（一個用戶 ↔ 一個 AI Agent）

**目標架構**：
```
[Next.js 前端 (blobs/)] <--WebRTC Audio--> [LiveKit Server] <---> [Agent.py]
        |                                                              |
   麥克風輸入 (已實作)                                          AI 推理 + MCP 工具
   Spline 3D 動畫                                              STT + TTS (OpenAI Realtime)
   聊天界面 (已實作)                                           BVC 降噪 + 業務邏輯
```

**一對一場景優化**：
- 每個用戶進入獨立房間（`room: user-${userId}`）
- 簡化 Participant 判斷邏輯（房間內只有 2 個參與者）
- 無需處理多用戶音訊混合或衝突
- 降低 LiveKit Server 資源需求

**關鍵改進（專家審核後）**：
- ✅ 前端啟用回音消除（AEC）防止自我干擾
- ✅ 處理瀏覽器自動播放限制
- ✅ 使用 Metadata 標記 Agent 身分
- ✅ Token API 安全強化（POST + CORS + Rate Limit）
- ✅ Agent 關閉視訊節省資源
- ✅ 雙層降噪（前端 AEC/NS + 後端 BVC）

---

## 現有架構分析

### 前端現狀 (blobs/)

**技術棧**：
- Next.js 15 (React 19 RC)
- TypeScript
- Spline 3D 動畫 (@splinetool/react-spline)
- 已實作功能：
  - 麥克風音訊捕獲（Web Audio API）
  - 音訊視覺化（音量條）
  - 聊天界面（對話記錄、訊息輸入）
  - 3D 角色動畫狀態機（idle/awake/reply）

**核心檔案**：
```
blobs/
├── app/
│   ├── page.tsx              # 主頁面
│   ├── layout.tsx            # 佈局
│   ├── SplineViewer.tsx      # 主元件（包含所有邏輯）
│   └── globals.css           # 樣式
├── package.json              # 依賴配置
└── next.config.js            # Next.js 配置
```

**現有音訊處理**：
- 使用 `navigator.mediaDevices.getUserMedia()` 捕獲麥克風
- Web Audio API 進行音量分析
- ⚠️ **問題**：目前關閉了 `echoCancellation`、`noiseSuppression`、`autoGainControl`
- ⚠️ **風險**：可能導致回音和自我干擾
- 尚未連接到後端語音處理系統

### 後端現狀 (agent.py)

**技術棧**：
- LiveKit Agent SDK
- OpenAI Realtime Model (語音模型)
- MCP 伺服器整合（天氣、搜尋、QA 工具）

**音訊處理**：
- `RoomInputOptions` 配置音訊輸入
- `RoomOutputOptions` 配置 TTS 輸出
- `noise_cancellation.BVC()` 降噪處理（✅ 正確使用）
- ⚠️ **問題**：目前 `video_enabled=True`，但不需要視訊
- ⚠️ **需修正**：應設為 `False` 以節省資源

---

## 專家審核要點與修正

### 🔴 關鍵風險點（必須修正）

#### 1. 回音問題（最嚴重）
**問題**：前端關閉 AEC/NS/AGC，當頁面播放 Agent TTS 時，麥克風會收到回音並送回房間，造成「自我干擾」。

**解決方案**：
- **前端**：啟用瀏覽器原生 AEC/NS/AGC
- **後端**：保持 BVC 降噪
- **雙層保護**：前端 + 後端雙重降噪最穩定

**修正代碼**：
```typescript
// ✅ 正確設定
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    echoCancellation: true,    // 必須開啟
    noiseSuppression: true,    // 必須開啟
    autoGainControl: true,     // 必須開啟
    sampleRate: 48000,
    channelCount: 1
  }
});
```

#### 2. 自動播放限制
**問題**：Chrome/Safari 需要用戶手勢後才能播放有聲音訊，否則會被攔截。

**解決方案**：
- 加入「開始對話」按鈕（用戶手勢）
- 或先以 `muted=true` attach，待點擊後解除靜音

**修正代碼**：
```typescript
// ✅ 正確做法
const audioElement = new Audio();
audioElement.muted = true;  // 先靜音
track.attach(audioElement);
audioElement.play();        // 可以成功

// 用戶點擊按鈕後
audioElement.muted = false; // 解除靜音
```

#### 3. Agent 身分判定不穩
**問題**：使用 `participant.identity.includes('agent')` 字串判斷不穩健。

**解決方案**：使用 **Participant Metadata** 標記角色。

**修正代碼**：
```typescript
// ❌ 舊做法
if (participant.identity.includes('agent')) { ... }

// ✅ 新做法
room.on(RoomEvent.ParticipantMetadataChanged, (metadata, participant) => {
  const meta = JSON.parse(metadata || '{}');
  if (meta.role === 'agent') {
    // 處理 Agent 軌道
  }
});
```

**後端設定**：
```python
# agent.py 或透過 RoomService API 設定
# participant.update_metadata(json.dumps({"role": "agent"}))
```

#### 4. Token API 安全性
**問題**：使用 `GET` 請求，query string 可能被記錄；CORS 設為 `*` 風險高。

**解決方案**：
- 改為 `POST` 請求
- 限制 CORS 白名單
- 加入 Rate Limit
- 最小權限原則

**修正代碼**：見「階段 2.3 安全強化」

---

## 整合策略（修正版）

### 核心改動概覽

**前端 (blobs/)**：
1. 安裝 LiveKit JS SDK
2. 建立 LiveKit 連接邏輯（新增 `hooks/useLiveKit.ts`）
3. 將現有麥克風音訊串流發送到 LiveKit
4. 接收並播放 Agent TTS 音訊
5. 整合到現有的狀態機（idle/awake/reply）

**後端 (agent.py)**：
1. 調整 `RoomInputOptions` 接收前端音訊
2. 保留 STT/TTS 處理邏輯
3. 確保 MCP 工具呼叫不受影響

---

## 階段 1：前端 LiveKit 整合

### 1.1 安裝依賴

```bash
cd blobs
npm install livekit-client
```

### 1.2 建立 LiveKit Hook

**新增檔案：`blobs/app/hooks/useLiveKit.ts`**

```typescript
'use client';

import { useRef, useState, useCallback, useEffect } from 'react';
import { Room, RoomEvent, Track, LocalAudioTrack, Participant } from 'livekit-client';

export interface LiveKitConfig {
  url: string;
  token: string;
}

export interface AgentState {
  isSpeaking: boolean;
  isListening: boolean;
}

export function useLiveKit() {
  const roomRef = useRef<Room | null>(null);
  const localAudioTrackRef = useRef<LocalAudioTrack | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [agentAudioElement, setAgentAudioElement] = useState<HTMLAudioElement | null>(null);
  const [agentState, setAgentState] = useState<AgentState>({
    isSpeaking: false,
    isListening: false,
  });
  const [error, setError] = useState<Error | null>(null);

  // ✅ 簡化版：一對一場景下直接判斷（房間內只有 user 和 agent）
  const isAgentParticipant = useCallback((participant: Participant): boolean => {
    // 方法 1：使用 Metadata（推薦，更明確）
    try {
      const metadata = JSON.parse(participant.metadata || '{}');
      if (metadata.role === 'agent') return true;
    } catch {}

    // 方法 2：一對一場景簡化判斷
    // 房間內只有 2 個參與者，非本地參與者即為 Agent
    return participant.identity !== roomRef.current?.localParticipant.identity;
  }, []);

  // 連接到 LiveKit 房間
  const connect = useCallback(async (config: LiveKitConfig) => {
    try {
      const room = new Room({
        // 啟用自適應串流和降噪
        adaptiveStream: true,
        dynacast: true,
      });
      roomRef.current = room;

      // 監聽連接事件
      room.on(RoomEvent.Connected, () => {
        console.log('✅ Connected to LiveKit room');
        setIsConnected(true);
        setError(null);
      });

      room.on(RoomEvent.Disconnected, (reason) => {
        console.log('❌ Disconnected from LiveKit room:', reason);
        setIsConnected(false);
        setAgentState({ isSpeaking: false, isListening: false });
      });

      // ✅ 監聽 Metadata 變更（用於識別 Agent）
      room.on(RoomEvent.ParticipantMetadataChanged, (metadata, participant) => {
        console.log('📝 Participant metadata changed:', participant.identity, metadata);

        if (isAgentParticipant(participant)) {
          console.log('✅ Agent participant identified:', participant.identity);
        }
      });

      // ✅ 監聽遠端音訊軌道（Agent TTS） - 改用 Metadata 判斷
      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        console.log('🎵 Track subscribed:', track.kind, participant.identity);

        if (track.kind === Track.Kind.Audio && isAgentParticipant(participant)) {
          const audioElement = new Audio();

          // ✅ 處理自動播放限制：先靜音
          audioElement.muted = true;
          track.attach(audioElement);

          audioElement.play().then(() => {
            console.log('✅ Agent TTS audio attached and playing (muted)');
            // 500ms 後解除靜音（給用戶時間準備）
            setTimeout(() => {
              audioElement.muted = false;
              console.log('🔊 Audio unmuted');
            }, 500);
          }).catch((err) => {
            console.error('❌ Autoplay failed:', err);
            setError(new Error('自動播放被阻擋，請點擊頁面任意處啟用音訊'));
          });

          setAgentAudioElement(audioElement);

          // 監聽播放狀態
          audioElement.addEventListener('play', () => {
            setAgentState(prev => ({ ...prev, isSpeaking: true }));
          });

          audioElement.addEventListener('pause', () => {
            setAgentState(prev => ({ ...prev, isSpeaking: false }));
          });

          audioElement.addEventListener('ended', () => {
            setAgentState(prev => ({ ...prev, isSpeaking: false }));
          });
        }
      });

      // 監聽錯誤
      room.on(RoomEvent.ConnectionQualityChanged, (quality, participant) => {
        if (quality === 'poor') {
          console.warn('⚠️ Connection quality is poor for:', participant.identity);
        }
      });

      // 連接到房間
      await room.connect(config.url, config.token);

      return room;
    } catch (error) {
      console.error('Failed to connect to LiveKit:', error);
      setError(error as Error);
      throw error;
    }
  }, [isAgentParticipant]);

  // 發布麥克風音訊
  const publishMicrophone = useCallback(async (stream: MediaStream) => {
    if (!roomRef.current) {
      throw new Error('Room not connected');
    }

    try {
      const audioTrack = new LocalAudioTrack(stream.getAudioTracks()[0], {
        name: 'microphone',
      });

      await roomRef.current.localParticipant.publishTrack(audioTrack, {
        name: 'microphone',
        // 確保音訊優先級
        audioPriority: 'high',
      });

      localAudioTrackRef.current = audioTrack;
      setIsPublishing(true);
      setAgentState(prev => ({ ...prev, isListening: true }));

      console.log('✅ Microphone published to LiveKit');
    } catch (error) {
      console.error('Failed to publish microphone:', error);
      setError(error as Error);
      throw error;
    }
  }, []);

  // 停止發布麥克風
  const unpublishMicrophone = useCallback(async () => {
    if (localAudioTrackRef.current && roomRef.current) {
      await roomRef.current.localParticipant.unpublishTrack(localAudioTrackRef.current);
      localAudioTrackRef.current.stop();
      localAudioTrackRef.current = null;
      setIsPublishing(false);
      setAgentState(prev => ({ ...prev, isListening: false }));
      console.log('🛑 Microphone unpublished');
    }
  }, []);

  // ✅ 手動解除靜音（處理自動播放限制）
  const unmuteAgentAudio = useCallback(() => {
    if (agentAudioElement) {
      agentAudioElement.muted = false;
      console.log('🔊 Agent audio unmuted by user interaction');
    }
  }, [agentAudioElement]);

  // 斷開連接
  const disconnect = useCallback(async () => {
    if (roomRef.current) {
      await roomRef.current.disconnect();
      roomRef.current = null;
      setIsConnected(false);
      setIsPublishing(false);
      setAgentState({ isSpeaking: false, isListening: false });
      console.log('🔌 Disconnected from room');
    }
  }, []);

  // 清理資源
  useEffect(() => {
    return () => {
      disconnect();
      if (agentAudioElement) {
        agentAudioElement.pause();
        agentAudioElement.src = '';
      }
    };
  }, [disconnect, agentAudioElement]);

  return {
    connect,
    disconnect,
    publishMicrophone,
    unpublishMicrophone,
    unmuteAgentAudio,
    isConnected,
    isPublishing,
    agentState,
    agentAudioElement,
    error,
  };
}
```

### 1.3 整合到 SplineViewer

**修改：`blobs/app/SplineViewer.tsx`**

主要變更點：

```typescript
// ===== 1. 導入 LiveKit hook =====
import { useLiveKit } from './hooks/useLiveKit';

// ===== 2. 在元件內使用 LiveKit =====
export default function SplineViewer() {
  const {
    connect,
    publishMicrophone,
    unpublishMicrophone,
    unmuteAgentAudio,
    isConnected,
    isPublishing,
    agentState,
    error: livekitError
  } = useLiveKit();

  // 新增狀態：處理自動播放
  const [audioPermissionGranted, setAudioPermissionGranted] = useState(false);

  // ===== 3. 連接 LiveKit（需用戶手勢觸發） =====
  // ✅ 改為用戶點擊後才連接（處理自動播放限制）
  async function handleStartConversation() {
    try {
      // 生成唯一用戶 ID（一對一場景）
      const userId = `user-${Date.now()}`;

      // 從後端獲取 token（改為 POST）
      const response = await fetch('http://localhost:5000/get-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          user_name: '嘉義客服用戶',
          room: `chiayi-${userId}`,  // ✅ 一對一：每個用戶獨立房間
        }),
      });

      const { token, url } = await response.json();
      await connect({ url, token });

      // 用戶手勢已取得，可以播放音訊
      setAudioPermissionGranted(true);

      // 自動啟動錄音
      await startRecording();
    } catch (error) {
      console.error('Failed to start conversation:', error);
      alert('連接失敗，請檢查網路或聯繫管理員');
    }
  }

  // ===== 4. 修改 startRecording 函數（✅ 啟用 AEC/NS/AGC） =====
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          // ✅ 必須開啟以防止回音
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 48000,
          channelCount: 1,
          // 可選：低延遲優化
          latency: 0.01,
        }
      });
      micStreamRef.current = stream;

      // 發布到 LiveKit
      if (isConnected) {
        await publishMicrophone(stream);
      }

      // 保留原有的視覺化邏輯
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = 0.8;
      analyserRef.current = analyser;

      source.connect(analyser);

      setIsRecording(true);
      setState('awake');  // 切換到喚醒狀態
      startAwakeAnimation();
      analyzeAudio();
    } catch (error) {
      console.error('無法存取麥克風:', error);

      // ✅ 更詳細的錯誤訊息
      if (error.name === 'NotAllowedError') {
        alert('請允許麥克風權限以開始對話');
      } else if (error.name === 'NotFoundError') {
        alert('找不到麥克風設備，請檢查設備連接');
      } else {
        alert(`麥克風初始化失敗：${error.message}`);
      }
    }
  }

  // ===== 5. 修改 stopRecording 函數 =====
  async function stopRecording() {
    // 取消發布 LiveKit 音訊
    await unpublishMicrophone();

    // 保留原有的清理邏輯
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(track => track.stop());
      micStreamRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    setIsRecording(false);
    setAudioLevel(0);
    setState('idle');  // 回到閒置狀態
    startIdleAnimation();
  }

  // ===== 6. 整合 Agent 狀態到動畫 =====
  useEffect(() => {
    if (agentState.isSpeaking) {
      setState('reply');
      startReplyAnimation();
    } else if (isPublishing) {
      setState('awake');
      startAwakeAnimation();
    } else {
      setState('idle');
      startIdleAnimation();
    }
  }, [agentState.isSpeaking, isPublishing]);

  // ===== 7. 顯示錯誤提示 =====
  useEffect(() => {
    if (livekitError) {
      console.error('LiveKit Error:', livekitError);
      // 可整合到 UI 顯示
    }
  }, [livekitError]);

  // ===== 8. 在 UI 中加入「開始對話」按鈕 =====
  return (
    <div className="app-container">
      {/* 左側：Spline 動畫區 */}
      <div className="left-panel">
        {/* ... Spline 元件 ... */}

        {/* ✅ 新增：開始對話按鈕（處理自動播放限制） */}
        {!isConnected && (
          <button
            className="start-conversation-button"
            onClick={handleStartConversation}
          >
            🎙️ 開始語音對話
          </button>
        )}

        {/* ✅ 顯示連接狀態 */}
        <div className="status-indicator">
          {!isConnected && '🔴 未連接'}
          {isConnected && !isPublishing && '🟡 已連接'}
          {isConnected && isPublishing && !agentState.isSpeaking && '🟢 聆聽中'}
          {agentState.isSpeaking && '💬 AI 回應中'}
        </div>

        {/* ✅ 錯誤提示 */}
        {livekitError && (
          <div className="error-message">
            ⚠️ {livekitError.message}
            <button onClick={unmuteAgentAudio}>點此啟用音訊</button>
          </div>
        )}

        {/* 原有的控制按鈕和視覺化 */}
        {/* ... */}
      </div>

      {/* 右側：聊天區 */}
      {/* ... 保持不變 ... */}
    </div>
  );
}
```

**關鍵修正說明**：
1. ✅ `getUserMedia` 開啟 AEC/NS/AGC（防止回音）
2. ✅ 加入「開始對話」按鈕（用戶手勢觸發連接）
3. ✅ 使用 POST 請求獲取 token（更安全）
4. ✅ 整合 Agent 狀態到 Spline 動畫
5. ✅ 詳細錯誤處理和用戶提示

---

## 階段 2：Token 管理服務（安全強化版）

### 2.1 建立 Token API（✅ 專家審核修正版 - FastAPI）

**新增檔案：`token_server.py`**

```python
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from livekit import api
import os
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

        if not any(re.match(pattern, body.room) for pattern in allowed_patterns):
            logger.warning(f"Unauthorized room access attempt: {body.room}")
            raise HTTPException(status_code=403, detail="Invalid room name")

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
        token.with_ttl(6 * 60 * 60)  # 6 hours

        logger.info(f"Token generated for user: {body.user_id}, room: {body.room}")

        return TokenResponse(
            token=token.to_jwt(),
            url=os.getenv('LIVEKIT_URL'),
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
```

### 2.2 環境變數配置

**更新 `.env` 檔案**：

```bash
# LiveKit 設定
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Token API 設定
TOKEN_API_PORT=5000
FLASK_ENV=development  # production 環境改為 'production'

# CORS 設定（生產環境必須指定）
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com

# OpenAI/Google API
GOOGLE_API_KEY=your-google-api-key
# 或
OPENAI_API_KEY=your-openai-api-key
```

### 2.3 安裝依賴

```bash
pip install fastapi uvicorn slowapi livekit python-dotenv
```

### 2.4 生產環境部署建議

**使用 Uvicorn**：

```bash
# 開發環境
python token_server.py

# 生產環境（單 worker）
uvicorn token_server:app --host 0.0.0.0 --port 5000

# 生產環境（多 worker）
uvicorn token_server:app --host 0.0.0.0 --port 5000 --workers 4
```

**使用 Gunicorn + Uvicorn Workers**（推薦）：

```bash
# 安裝 gunicorn
pip install gunicorn

# 啟動（4 個 uvicorn worker）
gunicorn token_server:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:5000
```

**使用 Docker**：

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY token_server.py .
COPY .env .

EXPOSE 5000

CMD ["uvicorn", "token_server:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "4"]
```

**API 文檔**：
FastAPI 自動生成 API 文檔，啟動後訪問：
- Swagger UI: `http://localhost:5000/docs`
- ReDoc: `http://localhost:5000/redoc`

---

## 階段 3：Agent 端調整（✅ 專家審核修正版）

### 3.1 修改 agent.py

**關鍵改動**：

```python
# agent.py - ✅ 專家審核修正版

import logging
import json
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, llm, RoomOutputOptions
from livekit.plugins import (
    google,
    openai,
    noise_cancellation,
)
from livekit.agents import mcp as mcp_client
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import (
    get_weather,
    search_web,
    qa_find_answer,
    qa_search_by_tag,
    qa_search_questions,
    qa_list_tags,
)
from log_config import setup_logging

setup_logging(level=logging.INFO, disable_duplicate=True)
agent_logger = logging.getLogger("core.agent")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=openai.realtime.RealtimeModel(
                voice="marin",
                temperature=0.8,
                speed=1.2,
            ),
            tools=[
                get_weather,
                qa_find_answer,
                qa_search_by_tag,
                qa_search_questions,
                qa_list_tags,
            ],
        )

    async def on_enter(self):
        agent_logger.info("Assistant agent has entered the room")

    async def on_exit(self):
        agent_logger.info("Assistant agent has exited the room")

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ):
        agent_logger.info(
            f"User turn completed. Message: {new_message.text[:50]}..."
        )


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()

    # ✅ 設定 Agent Metadata（讓前端可以識別）
    async def on_room_connected():
        try:
            await ctx.room.local_participant.update_metadata(
                json.dumps({"role": "agent", "name": "嘉義客服 AI"})
            )
            agent_logger.info("✅ Agent metadata set successfully")
        except Exception as e:
            agent_logger.error(f"Failed to set metadata: {e}")

    ctx.room.on("connected", on_room_connected)

    # 訂閱 ASR 轉錄事件
    def on_user_transcribed(event):
        event_type = "asr_final" if event.is_final else "asr_interim"
        agent_logger.info(f"[ASR] User said ({event_type}): {event.transcript}")

    session.on("user_input_transcribed", on_user_transcribed)

    # 訂閱 LLM 生成事件
    def on_agent_started_speaking(event):
        if hasattr(event, 'content'):
            agent_logger.info(f"[LLM] Assistant generating: {event.content}")

    session.on("agent_started_speaking", on_agent_started_speaking)

    # 訂閱對話項目新增事件
    def on_conversation_item(event):
        if hasattr(event, 'item') and hasattr(event.item, 'role'):
            if event.item.role == 'assistant':
                content = event.item.content if hasattr(event.item, 'content') else ''
                agent_logger.info(f"[TTS] Assistant said: {content}")

    session.on("conversation_item_added", on_conversation_item)

    # ✅ 關鍵修正：調整音訊配置
    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            video_enabled=False,  # ✅ 關閉視訊節省資源
            noise_cancellation=noise_cancellation.BVC(),  # ✅ 保留 BVC 降噪
        ),
        room_output_options=RoomOutputOptions(
            transcription_enabled=True,  # 啟用轉錄
            audio_enabled=True,          # ✅ 確認啟用音訊輸出（TTS）
        ),
    )

    await ctx.connect()

    # 生成初始問候
    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
```

### 3.2 修正說明

**✅ 主要變更**：

1. **關閉視訊** (`video_enabled=False`)：
   - 節省網路頻寬和伺服器資源
   - 符合語音專用場景

2. **保留 BVC 降噪** (`noise_cancellation.BVC()`)：
   - 前端 AEC/NS/AGC + 後端 BVC = 雙層降噪
   - 對多說話者和環境音效果最佳

3. **設定 Agent Metadata**：
   - 前端可以透過 `metadata.role === 'agent'` 識別
   - 避免字串判斷的不穩定性

4. **確認音訊輸出啟用**：
   - `audio_enabled=True` 確保 TTS 音訊會發布到房間
   - 前端可以正常接收和播放

**保持不變**：
- STT/TTS 由 OpenAI Realtime Model 處理
- MCP 工具整合完全不受影響
- 日誌和事件監聽邏輯保留

---

## 階段 4：狀態同步與動畫整合

### 4.1 整合語音狀態到 Spline 動畫

**修改：`blobs/app/SplineViewer.tsx`**

```typescript
// 在 useLiveKit hook 中加入狀態監聽
const { agentAudioElement } = useLiveKit();

useEffect(() => {
  if (!agentAudioElement) return;

  // 監聽 Agent 開始說話
  agentAudioElement.addEventListener('play', () => {
    setState('reply');  // 切換到回覆動畫
    startReplyAnimation();
  });

  // 監聽 Agent 結束說話
  agentAudioElement.addEventListener('ended', () => {
    setState('awake');  // 切換回喚醒狀態
    startAwakeAnimation();
  });

  return () => {
    agentAudioElement.removeEventListener('play', () => {});
    agentAudioElement.removeEventListener('ended', () => {});
  };
}, [agentAudioElement]);

// 修改錄音狀態與喚醒狀態的連動
function toggleRecording() {
  if (isRecording) {
    stopRecording();
    setState('idle');  // 停止錄音回到閒置
    startIdleAnimation();
  } else {
    startRecording();
    setState('awake');  // 開始錄音切換到喚醒
    startAwakeAnimation();
  }
}
```

### 4.2 聊天記錄整合（可選）

如果需要顯示語音轉文字的對話記錄，可以透過 WebSocket 或輪詢方式從 Agent 獲取轉錄文字。

---

## 階段 5：錯誤處理與用戶體驗

### 5.1 前端錯誤處理

**新增：`blobs/app/components/ErrorBoundary.tsx`**

```typescript
'use client';

import { useEffect } from 'react';

export function LiveKitErrorHandler({
  isConnected,
  error
}: {
  isConnected: boolean;
  error: Error | null;
}) {
  useEffect(() => {
    if (!isConnected && error) {
      // 顯示錯誤提示
      console.error('LiveKit Error:', error);

      // 可以整合到現有的 UI 提示
      alert(`連接失敗：${error.message}\n請檢查網路連接或聯繫管理員`);
    }
  }, [isConnected, error]);

  return null;
}
```

### 5.2 連接狀態指示器

在現有的 `status-indicator` 中加入 LiveKit 連接狀態：

```typescript
<div className="status-indicator">
  {!isConnected && '🔴 未連接'}
  {isConnected && !isPublishing && '🟡 已連接'}
  {isConnected && isPublishing && '🟢 通話中'}
  {state === 'reply' && '● 回覆中'}
</div>
```

---

## 階段 6：部署與測試

### 6.1 啟動順序

```bash
# 終端機 1：啟動 MCP 伺服器
python mcp_server.py

# 終端機 2：啟動 Token API
python token_server.py

# 終端機 3：啟動 LiveKit Agent
python agent.py dev

# 終端機 4：啟動 Next.js 前端
cd blobs
npm run dev
```

訪問：`http://localhost:3000`

### 6.2 測試檢查清單

**功能測試**
- [ ] 頁面載入後自動連接到 LiveKit
- [ ] 點擊麥克風按鈕可以開始錄音
- [ ] 麥克風音訊視覺化正常顯示
- [ ] 語音可以被 Agent 接收並轉錄
- [ ] Agent TTS 回應可以播放
- [ ] Spline 動畫狀態正確切換（awake → reply）
- [ ] 對話記錄正確顯示（如果實作）
- [ ] MCP 工具（天氣、QA）可以正確呼叫

**效能測試**
- [ ] 端到端延遲 < 2 秒
- [ ] 音訊品質良好（無雜訊、無回音）
- [ ] 連續對話 5 分鐘無異常
- [ ] 瀏覽器效能正常（FPS > 30）

**跨瀏覽器測試**
- [ ] Chrome（推薦）
- [ ] Edge
- [ ] Firefox
- [ ] Safari（macOS）

---

## 階段 7：優化與擴展

### 7.1 音訊品質優化

**前端音訊處理**：
```typescript
// 使用更高品質的音訊配置
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
    sampleRate: 48000,      // 高採樣率
    channelCount: 1,        // 單聲道
    latency: 0.01,          // 低延遲
  }
});
```

### 7.2 對話記錄持久化

可以將語音轉文字的對話記錄儲存到資料庫或 localStorage：

```typescript
// 儲存對話記錄
useEffect(() => {
  localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
}, [chatHistory]);

// 載入對話記錄
useEffect(() => {
  const saved = localStorage.getItem('chatHistory');
  if (saved) {
    setChatHistory(JSON.parse(saved));
  }
}, []);
```

### 7.3 一對一場景資源優化

針對一對一對話場景的特殊優化：

```python
# agent.py - 針對一對一場景優化
async def entrypoint(ctx: agents.JobContext):
    # 一對一場景：無需等待多個參與者
    await ctx.connect()

    session = AgentSession()
    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVC(),
        ),
        room_output_options=RoomOutputOptions(
            audio_enabled=True,
        ),
    )

    # 立即生成問候（無需等待其他參與者）
    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )
```

**一對一場景優勢**：
- ✅ 無需處理多用戶音訊混合
- ✅ 簡化 Participant 判斷邏輯
- ✅ 降低伺服器資源需求
- ✅ 更快的連接和響應時間

---

## 架構圖

```
┌─────────────────────────────────────────────────────────────┐
│                    使用者瀏覽器                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Next.js 前端 (localhost:3000)                      │   │
│  │  ├─ SplineViewer.tsx (3D 動畫 + UI)                 │   │
│  │  ├─ useLiveKit.ts (LiveKit 連接邏輯)                │   │
│  │  └─ Web Audio API (麥克風 + 視覺化)                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│                    WebRTC Audio                              │
│                           ▼                                  │
└─────────────────────────────────────────────────────────────┘

                           ▼
                    WebSocket/UDP
                           ▼

┌─────────────────────────────────────────────────────────────┐
│                   LiveKit Server                             │
│              (wss://your-server.com)                         │
└─────────────────────────────────────────────────────────────┘

                           ▼
                    WebSocket/gRPC
                           ▼

┌─────────────────────────────────────────────────────────────┐
│               Python 後端服務                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  agent.py (LiveKit Agent)                           │   │
│  │  ├─ OpenAI Realtime Model (STT + TTS)               │   │
│  │  ├─ AgentSession (對話管理)                         │   │
│  │  └─ MCP 工具整合                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│                    HTTP/SSE                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  mcp_server.py (MCP 伺服器)                         │   │
│  │  ├─ 天氣查詢 (wttr.in)                              │   │
│  │  ├─ 網頁搜尋 (DuckDuckGo)                           │   │
│  │  └─ QA 系統 (嘉義旅遊資料)                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  token_server.py (Flask API)                        │   │
│  │  └─ GET /get-token (生成 LiveKit Token)            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 技術決策說明

### 為何保留 Web Audio API？

雖然 LiveKit 處理音訊傳輸，但前端仍需要 Web Audio API 用於：
1. **音訊視覺化**（音量條動畫）
2. **本地音訊監控**（確認麥克風正常運作）
3. **未來擴展**（音訊效果、降噪濾鏡）

### 為何不移除現有聊天界面？

保留文字聊天界面的好處：
1. **備用方案**：網路不佳時仍可文字互動
2. **記錄查看**：用戶可回顧對話歷史
3. **多模態互動**：語音 + 文字混合使用

### 為何使用 Custom Hook？

`useLiveKit` hook 的優勢：
1. **邏輯分離**：LiveKit 邏輯與 UI 邏輯解耦
2. **可測試性**：可以獨立測試 LiveKit 功能
3. **可重用性**：未來可在其他元件中重用
4. **型別安全**：TypeScript 完整型別支援

---

## 後續優化方向

1. **語音活動檢測 (VAD)**：自動偵測用戶開始/停止說話
2. **斷線重連機制**：網路中斷後自動重新連接
3. **音訊編碼優化**：根據網路狀況動態調整編碼品質
4. **多語言支援**：英文、中文語音識別切換
5. **行動端適配**：針對手機瀏覽器優化音訊處理
6. **對話情緒分析**：根據語音情緒調整 Spline 動畫表現

---

## 常見問題

### Q1: LiveKit 連接失敗怎麼辦？

**檢查清單**：
1. 確認 `.env` 中的 `LIVEKIT_URL`、`LIVEKIT_API_KEY`、`LIVEKIT_API_SECRET` 正確
2. 確認 Token API (`token_server.py`) 正在運行
3. 檢查瀏覽器 Console 是否有 CORS 錯誤
4. 確認 LiveKit Server 可以正常訪問

### Q2: 聽不到 Agent 的聲音？

**檢查清單**：
1. 確認瀏覽器允許自動播放音訊
2. 檢查音量設定（瀏覽器、系統、耳機）
3. 查看 Console 是否有音訊播放錯誤
4. 確認 Agent 的 `room_output_options.audio_enabled = True`

### Q3: 麥克風無法錄音？

**檢查清單**：
1. 瀏覽器是否允許麥克風權限
2. 系統麥克風是否正常運作
3. 是否有其他應用程式佔用麥克風
4. 檢查 `getUserMedia` 錯誤訊息

### Q4: 語音延遲太高？

**優化方向**：
1. 使用更低的 `latency` 設定
2. 檢查網路延遲（ping LiveKit Server）
3. 降低音訊採樣率（48000 → 24000）
4. 使用更快的 TTS 模型

---

## 總結

本計畫在現有 Next.js + Spline 3D 前端的基礎上，最小化侵入地整合 LiveKit 即時語音功能：

**優勢**：
- 保留所有現有功能（3D 動畫、聊天界面、音訊視覺化）
- 使用 Custom Hook 實現邏輯分離
- 支援語音 + 文字多模態互動
- 良好的型別安全和可維護性

**實作複雜度**：
- 新增檔案：2 個（`useLiveKit.ts`、`token_server.py`）
- 修改檔案：2 個（`SplineViewer.tsx`、`agent.py`）
- 依賴安裝：2 個套件（前端 `livekit-client`、後端 `flask flask-cors`）

**預估工時**：
- 前端整合：3-4 小時
- 後端調整：1-2 小時
- 測試調試：2-3 小時
- **總計**：6-9 小時

---

## 開始實作

準備好開始了嗎？建議按以下順序進行：

1. **階段 1**：安裝依賴並建立 `useLiveKit` hook
2. **階段 2**：建立 Token API
3. **階段 3**：整合到 `SplineViewer.tsx`
4. **階段 4**：調整 `agent.py`
5. **階段 5**：測試與調試
6. **階段 6**：優化與部署

需要協助任何階段的實作，請隨時告知！
