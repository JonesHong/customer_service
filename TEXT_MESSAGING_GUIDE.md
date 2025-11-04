# 文字訊息整合指南

## 概述

本指南說明如何在 LiveKit 語音 Agent 系統中整合文字訊息功能，使用戶能透過文字輸入與 Agent 互動，Agent 透過 TTS 回覆。

## 核心架構

### 訊息流程

```
前端 (TypeScript)                     後端 (Python)
    |                                      |
    | publishData({                        |
    |   type: 'chat',                      |
    |   text: '使用者訊息',                |
    |   topic: 'lk.chat'                   |
    | })                                   |
    |                                      |
    |------------ LiveKit Server -------->|
    |                                      |
    |                          data_received event
    |                                      |
    |                          解析 DataPacket
    |                                      |
    |                          創建 TextInputEvent
    |                                      |
    |                          on_text_message()
    |                                      |
    |                          generate_reply()
    |                                      |
    |<------------ TTS 語音回覆 -----------|
```

## 關鍵技術發現

### 1. publishData 觸發 data_received 事件

**重要發現（來自 DeepWiki 研究）：**

> `publishData` API 會觸發 `data_received` 事件，**不是** `text_stream_handler`。

**這意味著：**

| 方法 | 觸發事件 | 用途 |
|------|---------|------|
| `publishData()` | `data_received` | 單次數據傳輸（如聊天訊息） |
| 文字串流 | `stream_header_received` → `text_stream_handler` | 多段文字串流 |

**正確實作：**

```python
# ✅ 正確：使用 data_received 事件處理 publishData
@ctx.room.on("data_received")
def on_data_packet_received(data_packet: rtc.DataPacket):
    # 處理 publishData 發送的訊息
    text = data_packet.data.decode('utf-8')
    payload = json.loads(text)
    # ...

# ❌ 錯誤：使用 text_stream_handler
# 這只處理串流事件，不處理 publishData
```

### 2. WorkerPermissions 必須包含 can_publish_data

```python
worker_options = agents.WorkerOptions(
    entrypoint_fnc=entrypoint,
    permissions=WorkerPermissions(
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,      # ✅ 必須為 True
        can_update_metadata=True
    ),
)
```

### 3. Handler 註冊必須在 session.start() 之前

```python
async def entrypoint(ctx: JobContext):
    # ✅ 正確順序
    ctx.room.on("data_received", handler)  # 1. 先註冊 handler
    await session.start()                   # 2. 再啟動 session

    # ❌ 錯誤順序
    await session.start()                   # 1. 先啟動
    ctx.room.on("data_received", handler)  # 2. 後註冊（太晚了！）
```

## 前端實作

### TypeScript/React 實作

```typescript
// useLiveKit.ts

const sendTextMessage = useCallback(async (text: string) => {
  if (!roomRef.current) {
    throw new Error('Room not connected');
  }

  // 創建 JSON payload
  const payload = JSON.stringify({
    type: 'chat',
    text: text,
    timestamp: Date.now(),
    sender: roomRef.current.localParticipant.identity
  });

  // 編碼為 bytes
  const encoder = new TextEncoder();
  const data = encoder.encode(payload);

  // 使用 publishData 發送（不是 sendChatMessage）
  await roomRef.current.localParticipant.publishData(data, {
    reliable: true,
    topic: 'lk.chat'  // 必須指定 topic
  });

  console.log('✅ Text message sent via publishData');
}, []);
```

**關鍵點：**
- 使用 `publishData` 而非 `sendChatMessage`
- 必須指定 `topic: 'lk.chat'` 以匹配後端
- 使用 JSON 格式傳輸結構化數據
- 設置 `reliable: true` 確保可靠傳輸

## 後端實作

### Python/LiveKit Agents 實作

```python
# agent.py

import json
import asyncio
from livekit import rtc
from livekit.agents import TextInputEvent

async def entrypoint(ctx: JobContext):
    # 創建 session
    session = await ctx.create_session(...)

    # 定義文字訊息回調
    async def on_text_message(sess: AgentSession, event: TextInputEvent):
        """處理文字訊息"""
        user_text = event.text.strip()
        participant = event.participant

        agent_logger.info(f"💬 Received: {user_text} from {participant.identity}")

        # 生成回覆（會透過 TTS 輸出）
        await sess.generate_reply(user_input=user_text, instructions=None)

    # 定義 DataPacket 處理器
    def on_data_packet_received(data_packet: rtc.DataPacket):
        """處理 publishData 發送的 DataPacket"""
        agent_logger.info("🎯 Data packet received!")

        try:
            # 解碼二進制數據
            text = data_packet.data.decode('utf-8')
            agent_logger.info(f"📥 Decoded: {text}")

            # 解析 JSON
            payload = json.loads(text)

            # 檢查是否為聊天訊息
            if payload.get('type') == 'chat':
                user_text = payload.get('text', '')
                participant = data_packet.participant

                if participant:
                    # 創建 TextInputEvent
                    event = TextInputEvent(text=user_text, participant=participant)

                    # 異步處理
                    asyncio.create_task(on_text_message(session, event))
                else:
                    agent_logger.warning("⚠️ No participant found")

        except Exception as e:
            agent_logger.error(f"❌ Error: {e}")

    # ✅ 關鍵：在 session.start() 之前註冊
    ctx.room.on("data_received", on_data_packet_received)
    agent_logger.info("✅ Registered data_received handler")

    # 啟動 session
    await session.start()
    agent_logger.info("✅ Session started")
```

**關鍵點：**
- 使用 `room.on("data_received", handler)` 而非 `text_stream_handler`
- Handler 簽名必須為 `def handler(data_packet: rtc.DataPacket)`
- 必須在 `session.start()` 之前註冊
- 使用 `asyncio.create_task()` 處理異步回調
- 使用 `data_packet.participant` 獲取發送者信息

## 測試流程

### 步驟 1：啟動診斷工具（可選）

```bash
# 終端 1
python diagnostic_tool.py
```

這個工具會以觀察者身份連接房間，監聽所有 `data_received` 事件。

### 步驟 2：啟動 Agent

```bash
# 終端 2
python agent.py dev
```

### 步驟 3：前端發送測試訊息

從網頁前端發送測試訊息，例如："你好"

### 步驟 4：驗證日誌

**診斷工具應該顯示：**
```
🎯 [DATA_RECEIVED #1] DATA PACKET RECEIVED!
📊 [DATA_RECEIVED] Topic: lk.chat
📥 [DATA_RECEIVED] Decoded text: {"type":"chat","text":"你好",...}
```

**Agent 應該顯示：**
```
🎯 [DATA_PACKET] Data packet received!
📥 [DATA_PACKET] Decoded text: {"type":"chat","text":"你好",...}
💬 [CHAT] Received chat message: 你好
🔔 [TEXT_CALLBACK] *** TEXT MESSAGE CALLBACK TRIGGERED ***
```

**前端應該：**
- 收到 TTS 語音回覆
- 播放 Agent 的語音回覆

## 常見問題排查

### 問題 1：後端沒有收到任何訊息

**檢查項目：**
1. ✅ WorkerPermissions 是否設置 `can_publish_data=True`
2. ✅ Handler 是否在 `session.start()` 之前註冊
3. ✅ 使用 `data_received` 事件而非 `text_stream_handler`
4. ✅ Handler 簽名是否正確：`def handler(data_packet: rtc.DataPacket)`

**使用診斷工具：**
```bash
python diagnostic_tool.py
```

如果診斷工具收到但 Agent 沒收到 → Agent 配置問題
如果兩者都沒收到 → Server 或網絡問題

### 問題 2：收到訊息但解析失敗

**檢查項目：**
1. 前端是否正確編碼為 UTF-8
2. 前端是否發送有效的 JSON
3. 後端是否正確解碼 `data_packet.data`

**調試代碼：**
```python
# 在 handler 中添加
agent_logger.info(f"Raw data type: {type(data_packet.data)}")
agent_logger.info(f"Raw data: {data_packet.data}")
```

### 問題 3：Agent 沒有生成回覆

**檢查項目：**
1. `on_text_message` 回調是否被觸發
2. `generate_reply()` 是否正確調用
3. Agent 的 LLM 配置是否正確

**調試代碼：**
```python
async def on_text_message(sess: AgentSession, event: TextInputEvent):
    agent_logger.info("🔥 on_text_message called")
    agent_logger.info(f"🔥 User text: {event.text}")

    await sess.generate_reply(user_input=event.text, instructions=None)

    agent_logger.info("🔥 generate_reply completed")
```

## 完整檢查清單

### 前端

- [ ] 使用 `publishData` 而非 `sendChatMessage`
- [ ] 指定 `topic: 'lk.chat'`
- [ ] 發送 JSON 格式數據
- [ ] 設置 `reliable: true`
- [ ] 正確編碼為 UTF-8 bytes

### 後端

- [ ] WorkerPermissions 設置 `can_publish_data=True`
- [ ] 使用 `room.on("data_received", handler)`
- [ ] Handler 在 `session.start()` 之前註冊
- [ ] Handler 簽名正確：`def handler(data_packet: rtc.DataPacket)`
- [ ] 正確解碼和解析 DataPacket
- [ ] 創建 TextInputEvent 並調用回調
- [ ] 使用 `asyncio.create_task()` 處理異步

### 測試

- [ ] 診斷工具收到訊息
- [ ] Agent 收到訊息
- [ ] on_text_message 被觸發
- [ ] generate_reply 被調用
- [ ] TTS 回覆生成
- [ ] 前端收到並播放語音

## 相關文件

- `TEXT_MESSAGING_SOLUTION.md` - 完整技術方案
- `TEXT_MESSAGING_DEBUG.md` - 除錯指南
- `diagnostic_tool.py` - 診斷工具
- `PING_PONG_TEST.md` - Ping-Pong 測試指南

## 參考資料

本方案基於以下研究：
- LiveKit Client SDK JS 文檔（通過 DeepWiki）
- LiveKit Agents Python SDK 文檔（通過 DeepWiki）
- publishData 與 data_received 事件關係分析
- 實際測試和日誌分析
