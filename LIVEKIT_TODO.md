# LiveKit 整合 TODO List

## 📋 階段 1：前端 LiveKit 整合

- [x] 1.1 安裝 livekit-client 依賴
  ```bash
  cd blobs && npm install livekit-client
  ```

- [x] 1.2 建立 LiveKit Hook
  - [x] 新增 `blobs/app/hooks/useLiveKit.ts`
  - [x] 實作連接、發布、接收音訊邏輯
  - [x] 實作 Metadata 判斷 Agent
  - [x] 處理自動播放限制
  - [x] **修正為官方推薦的 track.attach() 用法**
  - [x] **新增 AudioPlaybackStatusChanged 事件處理**

- [x] 1.3 整合到 SplineViewer
  - [x] 修改 `blobs/app/SplineViewer.tsx`
  - [x] 啟用 AEC/NS/AGC（回音消除）
  - [x] 加入「開始對話」按鈕
  - [x] 整合 Agent 狀態到動畫
  - [x] 實作錯誤處理和狀態指示器
  - [x] 修復 React StrictMode 重複渲染導致斷線
  - [x] 新增「結束對話」按鈕控制連接
  - [x] 修復連接後自動開始錄音
  - [x] 改進 TTS 音訊播放（加入 DOM、設定音量）

## 📋 階段 2：Token 管理服務

- [x] 2.1 建立 Token API
  - [x] 新增 `token_server.py`（FastAPI + CORS + Rate Limit）
  - [x] 實作 POST `/get-token` 端點（Pydantic models）
  - [x] 加入安全驗證（房間白名單、最小權限）

- [x] 2.2 環境配置
  - [x] 更新 `.env`（LIVEKIT_URL、API_KEY、ALLOWED_ORIGINS）
  - [x] 安裝依賴：`pip install fastapi uvicorn slowapi livekit`

- [x] 2.3 安全強化
  - [x] 限制 CORS 白名單
  - [x] 設定 Rate Limit
  - [x] Token 權限最小化

## 📋 階段 3：Agent 端調整

- [x] 3.1 修改 agent.py
  - [x] 關閉視訊：`video_enabled=False`
  - [x] 保留 BVC 降噪
  - [x] 設定 Agent Metadata（role: "agent"）
  - [x] 確認音訊輸出啟用
  - [x] 修復 async callback 錯誤（使用 asyncio.create_task）
  - [x] 修復 ctx.room.sid 呼叫錯誤（移除括號）
  - [x] **修復音訊輸入未啟用問題**（`audio_enabled=True` in RoomInputOptions）
  - [x] **啟用 OpenAI Realtime VAD**（TurnDetection with server_vad）

## 📋 階段 4：部署與測試

- [x] 4.1 啟動服務（準備開始測試）
  ```bash
  # 終端機 1: MCP 伺服器
  python mcp_server.py

  # 終端機 2: Token API（Port 5001）
  python token_server.py

  # 終端機 3: LiveKit Agent（已修復 async callback）
  python agent.py dev

  # 終端機 4: Next.js 前端
  cd blobs && npm run dev
  ```

- [x] 4.2 功能測試
  - [x] 連接到 LiveKit（穩定連接）
  - [x] 麥克風錄音（成功發布）
  - [x] Agent TTS 播放（音訊連接成功）
  - [x] 動畫狀態切換（正確切換）
  - [x] 修復 React StrictMode 導致麥克風重複發布問題
  - [x] **修復 OpenAI Realtime 無音訊問題**（取消註解 generate_reply 調用）
  - [ ] MCP 工具呼叫（待測試語音指令）

- [ ] 4.3 效能測試
  - [ ] 端到端延遲 < 2 秒
  - [ ] 音訊品質（無回音）
  - [ ] 連續對話 5 分鐘

- [ ] 4.4 跨瀏覽器測試
  - [ ] Chrome
  - [ ] Edge
  - [ ] Firefox
  - [ ] Safari

## 📋 階段 5：優化（可選）

- [ ] 5.1 對話記錄持久化
- [ ] 5.2 多用戶支援
- [ ] 5.3 音訊品質優化

---

## 🔑 關鍵修正點（專家審核）

✅ **已納入計畫的重要改進**：
1. 前端啟用回音消除（AEC/NS/AGC）
2. 處理瀏覽器自動播放限制
3. 使用 Metadata 標記 Agent 身分
4. Token API 安全強化（POST + CORS + Rate Limit）
5. Agent 關閉視訊節省資源
6. 雙層降噪（前端 + 後端 BVC）

---

## 📚 參考資料

詳細實作細節請參考 `LIVEKIT_INTEGRATION_PLAN.md`：
- 完整程式碼範例
- 錯誤處理策略
- 架構圖
- 常見問題解答
