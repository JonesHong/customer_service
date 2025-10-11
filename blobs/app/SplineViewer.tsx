'use client';

import { useRef, useState, useEffect } from 'react';
import type { Application, SPEObject } from '@splinetool/runtime';
import { useLiveKit } from './hooks/useLiveKit';

type AnimationState = 'idle' | 'awake' | 'reply';

interface ChatMessage {
  text: string;
  timestamp: string;
  isUser: boolean;
}

export default function SplineViewer() {
  const splineRef = useRef<Application>();
  const sphereRef = useRef<SPEObject | null>(null);
  const [state, setState] = useState<AnimationState>('idle');
  const [SplineComponent, setSplineComponent] = useState<any>(null);
  const animationRef = useRef<NodeJS.Timeout | null>(null);
  const [currentMessage, setCurrentMessage] = useState<string>('');
  const messageTimerRef = useRef<NodeJS.Timeout | null>(null);
  const initialPositionRef = useRef<number>(0);
  const messageBubbleRef = useRef<HTMLDivElement>(null); // 訊息泡泡滾動容器

  // 聊天相關狀態
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [showChat, setShowChat] = useState<boolean>(true);

  // 麥克風相關狀態
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // ✅ LiveKit 整合
  const {
    connect,
    disconnect,
    publishMicrophone,
    unpublishMicrophone,
    unmuteAgentAudio,
    isConnected,
    isPublishing,
    agentState,
    error: livekitError,
    transcriptions,
    isUserSpeaking, // ✅ 新增
  } = useLiveKit();

  const [audioPermissionGranted, setAudioPermissionGranted] = useState(false);

  useEffect(() => {
    import('@splinetool/react-spline').then((mod) => {
      setSplineComponent(() => mod.default);
    });
  }, []);

  // 清理動畫和音訊
  useEffect(() => {
    return () => {
      if (animationRef.current) {
        clearInterval(animationRef.current);
      }
      if (messageTimerRef.current) {
        clearInterval(messageTimerRef.current);
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (micStreamRef.current) {
        micStreamRef.current.getTracks().forEach(track => track.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  // ✅ 同步 LiveKit transcriptions 到 chatHistory（顯示 streaming 效果）
  useEffect(() => {
    if (transcriptions.length > 0) {
      const lastTranscription = transcriptions[transcriptions.length - 1];

      const newMessage: ChatMessage = {
        // Interim 訊息結尾加上 "..." 表示正在進行中
        text: lastTranscription.isFinal
          ? lastTranscription.text
          : lastTranscription.text + '...',
        timestamp: lastTranscription.timestamp.toLocaleTimeString('zh-TW', {
          hour: '2-digit',
          minute: '2-digit'
        }),
        isUser: lastTranscription.role === 'user'
      };

      setChatHistory(prev => {
        // 檢查最後一則訊息是否為同角色的 interim 訊息（末尾有 "..."）
        if (prev.length > 0) {
          const lastMsg = prev[prev.length - 1];
          const isSameRole = lastMsg.isUser === newMessage.isUser;
          const isInterimMessage = lastMsg.text.endsWith('...');

          // 如果是同角色且最後一則是 interim（有 "..."），取代它
          if (isSameRole && isInterimMessage) {
            return [...prev.slice(0, -1), newMessage];
          }
        }

        // 否則新增新訊息
        return [...prev, newMessage];
      });
    }
  }, [transcriptions]);

  // 自動滾動到最新訊息（右側聊天區）
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  // ✅ 同步 transcriptions 到 currentMessage（顯示 Agent 即時字幕）
  useEffect(() => {
    if (transcriptions.length > 0) {
      const lastTranscription = transcriptions[transcriptions.length - 1];

      // 只顯示 Agent 的訊息（不顯示用戶自己說的話）
      if (lastTranscription.role === 'assistant') {
        // Interim 或 Final 都顯示，不清空
        setCurrentMessage(lastTranscription.text);

        // 自動滾動到底部（說話時）
        if (messageBubbleRef.current) {
          messageBubbleRef.current.scrollTop = messageBubbleRef.current.scrollHeight;
        }
      }
    }
  }, [transcriptions]);

  // ✅ 整合 Agent 狀態到動畫
  useEffect(() => {
    console.log('🎭 Animation state check:', {
      agentSpeaking: agentState.isSpeaking,
      userSpeaking: isUserSpeaking,
      currentState: state
    });

    // 優先級：使用者說話 > Agent 說話 > 閒置
    // ✅ 修正：使用者說話時應該中斷 Agent 動畫
    if (isUserSpeaking) {
      console.log('👤 User speaking - Switching to AWAKE animation');
      handleAwake();
    } else if (agentState.isSpeaking) {
      console.log('🤖 Agent speaking - Switching to REPLY animation');
      handleReply();
    } else {
      console.log('😴 Nobody speaking - Switching to IDLE animation');
      handleIdle();
    }
  }, [agentState.isSpeaking, isUserSpeaking]); // ✅ 用 isUserSpeaking 取代 isPublishing

  // ✅ 顯示錯誤提示
  useEffect(() => {
    if (livekitError) {
      console.error('LiveKit Error:', livekitError);
    }
  }, [livekitError]);

  function onLoad(spline: Application) {
    splineRef.current = spline;

    // 找到球體物件
    const sphere = spline.findObjectByName('Sphere');
    if (sphere) {
      sphereRef.current = sphere;
      // 記錄初始位置
      initialPositionRef.current = sphere.position.y;
      console.log('✅ Sphere found:', sphere.name, 'Initial Y:', initialPositionRef.current);
    } else {
      console.log('❌ Sphere not found!');
    }

    // 初始設定為閒置狀態
    startIdleAnimation();
  }

  function clearAnimation() {
    if (animationRef.current) {
      clearInterval(animationRef.current);
      animationRef.current = null;
    }
  }

  function startIdleAnimation() {
    clearAnimation();
    if (!sphereRef.current) return;

    const sphere = sphereRef.current;
    console.log('💤 閒置狀態：緩慢脈動');

    // 重置位置到初始位置
    sphere.position.y = initialPositionRef.current;
    sphere.scale.x = 1;
    sphere.scale.y = 1;
    sphere.scale.z = 1;

    let time = 0;
    animationRef.current = setInterval(() => {
      time += 0.03; // 非常慢
      const pulse = 1.0 + Math.sin(time) * 0.03; // 微小幅度
      sphere.scale.x = pulse;
      sphere.scale.y = pulse;
      sphere.scale.z = pulse;
    }, 50);

    splineRef.current?.play();
  }

  function startAwakeAnimation() {
    clearAnimation();
    if (!sphereRef.current) return;

    const sphere = sphereRef.current;
    console.log('❤️ 喚醒狀態：心跳脈動');

    // 重置位置到初始位置
    sphere.position.y = initialPositionRef.current;
    sphere.scale.x = 1;
    sphere.scale.y = 1;
    sphere.scale.z = 1;

    let time = 0;
    animationRef.current = setInterval(() => {
      time += 0.08; // 降低速度
      // 心跳效果：雙峰波形模擬真實心跳
      const heartbeat = Math.sin(time * 4) * 0.1 + Math.sin(time * 8) * 0.05;
      const pulse = 1.0 + heartbeat;
      sphere.scale.x = pulse;
      sphere.scale.y = pulse;
      sphere.scale.z = pulse;
    }, 40);

    splineRef.current?.play();
  }

  function startReplyAnimation() {
    clearAnimation();
    if (!sphereRef.current) return;

    const sphere = sphereRef.current;
    console.log('🎯 回覆狀態：上下跳動');

    let time = 0;

    // 線性插值函數
    const lerp = (a: number, b: number, t: number) => a * (1 - t) + b * t;

    animationRef.current = setInterval(() => {
      time += 0.1;
      // 史萊姆跳躍效果：Y 軸位置變化（基於初始位置）
      const jump = Math.abs(Math.sin(time * 2.5)) * 150; // 上下跳動幅度
      sphere.position.y = initialPositionRef.current + jump;

      // 真實物理彈跳變形
      const bounceProgress = jump / 150; // 0 = 底部, 1 = 頂部

      // 底部狀態 (t=0): 擠壓
      const squashY = 0.75; // Y 軸壓縮
      const stretchXZ = 1.3;  // XZ 軸拉伸

      // 頂部狀態 (t=1): 拉伸
      const stretchY = 1.08; // Y 軸拉伸
      const squashXZ = 0.95;  // XZ 軸壓縮

      // 使用 lerp 在兩種狀態之間插值
      const finalScaleY = lerp(squashY, stretchY, bounceProgress);
      const finalScaleXZ = lerp(stretchXZ, squashXZ, bounceProgress);

      sphere.scale.x = finalScaleXZ;
      sphere.scale.y = finalScaleY;
      sphere.scale.z = finalScaleXZ;
    }, 40);

    splineRef.current?.play();
  }

  // 模擬訊息列表 - 15 句話
  const mockMessages = [
    "嗨！我是你的 AI 助手 ✨",
    "今天過得怎麼樣呢？",
    "有什麼我可以幫忙的嗎？",
    "讓我們一起探索知識的世界吧！",
    "我隨時都在這裡陪伴你喔～",
    "遇到問題了嗎？跟我說說看！",
    "你知道嗎？我最喜歡回答問題了 😊",
    "每天都要開開心心的哦！",
    "學習新事物總是令人興奮呢！",
    "相信自己，你可以做到的！",
    "今天想聊些什麼呢？",
    "我會用心聆聽你的每一句話 💙",
    "別擔心，我們一起解決！",
    "你的好奇心讓世界變得更有趣～",
    "記得要好好休息，保持活力喔！"
  ];

  const messageIndexRef = useRef(0);

  // 獲取當前時間 HH:mm 格式
  function getCurrentTime(): string {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
  }

  // 發送訊息
  function handleSendMessage() {
    if (!inputText.trim()) return;

    // 添加用戶訊息
    const userMessage: ChatMessage = {
      text: inputText,
      timestamp: getCurrentTime(),
      isUser: true,
    };

    setChatHistory(prev => [...prev, userMessage]);
    setInputText('');

    // AI 回覆當前顯示的內容（1 秒後）
    setTimeout(() => {
      const aiResponse: ChatMessage = {
        text: currentMessage || "我現在沒有在說話喔～",
        timestamp: getCurrentTime(),
        isUser: false,
      };
      setChatHistory(prev => [...prev, aiResponse]);
    }, 1000);
  }

  // 處理 Enter 鍵送出
  function handleKeyPress(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  }

  // ✅ 開始對話（連接 LiveKit）
  async function handleStartConversation() {
    try {
      // 生成唯一用戶 ID（一對一場景）
      const timestamp = Date.now();
      const userId = `user-${timestamp}`;

      // 從後端獲取 token（改為 POST）
      const response = await fetch('http://localhost:5001/get-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          user_name: '嘉義客服用戶',
          room: `chiayi-user-${timestamp}`,  // ✅ 修正：直接使用 timestamp
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Token API error (${response.status}): ${errorText}`);
      }

      const data = await response.json();
      console.log('Token response:', { token: data.token?.substring(0, 50) + '...', url: data.url, room: data.room });

      if (!data.url || !data.token) {
        throw new Error('Invalid token response: missing url or token');
      }

      await connect({ url: data.url, token: data.token });

      // 用戶手勢已取得，可以播放音訊
      setAudioPermissionGranted(true);

      // ✅ 連接成功後自動開始錄音（只調用一次）
      await startRecording();
    } catch (error) {
      console.error('Failed to start conversation:', error);
      alert(`連接失敗：${(error as Error).message}`);
    }
  }

  // 分析音訊並更新音量
  function analyzeAudio() {
    if (!analyserRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);

    // 計算平均音量（頻域）
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const average = sum / dataArray.length;

    // 正規化到 0-1，提高靈敏度到 6 倍
    const normalizedLevel = Math.min((average / 255) * 6, 1);

    setAudioLevel(normalizedLevel);

    animationFrameRef.current = requestAnimationFrame(analyzeAudio);
  }

  // ✅ 修改 startRecording 函數（啟用 AEC/NS/AGC）
  async function startRecording() {
    // ✅ Guard: 防止重複調用（React StrictMode 保護）
    if (isRecording || micStreamRef.current) {
      console.log('⚠️ Recording already in progress, skipping duplicate call');
      console.log('   isRecording:', isRecording);
      console.log('   micStreamRef.current:', !!micStreamRef.current);
      return;
    }

    try {
      console.log('🎤 Starting microphone recording...');
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

      // 發布到 LiveKit（使用 roomRef 直接檢查，避免 state 時序問題）
      console.log('🎤 Attempting to publish microphone, isConnected:', isConnected);
      await publishMicrophone(stream);
      console.log('✅ Microphone publish completed');

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
      if ((error as any).name === 'NotAllowedError') {
        alert('請允許麥克風權限以開始對話');
      } else if ((error as any).name === 'NotFoundError') {
        alert('找不到麥克風設備，請檢查設備連接');
      } else {
        alert(`麥克風初始化失敗：${(error as Error).message}`);
      }
    }
  }

  // ✅ 修改 stopRecording 函數
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

  // 切換錄音狀態
  function toggleRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  function handleIdle() {
    setState('idle');
    startIdleAnimation();

    // 清除舊的計時器
    if (messageTimerRef.current) {
      clearInterval(messageTimerRef.current);
      messageTimerRef.current = null;
    }

    // 立即清空訊息
    setCurrentMessage('');

    // ✅ 閒置狀態：隨機顯示訊息（4-7秒間隔，不重複）
    const scheduleNextMessage = () => {
      // 隨機延遲 4-7 秒
      const delay = Math.random() * 3000 + 4000; // 4000-7000ms

      messageTimerRef.current = setTimeout(() => {
        // 隨機選擇一句話（避免與上次相同）
        let newIndex;
        do {
          newIndex = Math.floor(Math.random() * mockMessages.length);
        } while (newIndex === messageIndexRef.current && mockMessages.length > 1);

        messageIndexRef.current = newIndex;
        setCurrentMessage(mockMessages[newIndex]);

        // 顯示 4 秒後清空，然後排程下一次
        setTimeout(() => {
          setCurrentMessage('');
          scheduleNextMessage(); // 遞迴排程下一次
        }, 4000);
      }, delay);
    };

    // 開始排程
    scheduleNextMessage();
  }

  function handleAwake() {
    setState('awake');
    startAwakeAnimation();
    setCurrentMessage(''); // 清空訊息

    // 清除訊息輪換計時器
    if (messageTimerRef.current) {
      clearInterval(messageTimerRef.current);
      messageTimerRef.current = null;
    }
    messageIndexRef.current = 0;
  }

  function handleReply() {
    setState('reply');
    startReplyAnimation();

    // 顯示第一條訊息
    messageIndexRef.current = 0;
    // setCurrentMessage(mockMessages[0]);

    // 每 3 秒輪換下一條訊息
    if (messageTimerRef.current) {
      clearInterval(messageTimerRef.current);
    }

    // messageTimerRef.current = setInterval(() => {
    //   messageIndexRef.current = (messageIndexRef.current + 1) % mockMessages.length;
    //   setCurrentMessage(mockMessages[messageIndexRef.current]);
    // }, 3000);
  }

  if (!SplineComponent) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontSize: '20px',
        color: '#666'
      }}>
        Loading...
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* 左側：Spline 動畫區 */}
      <div className="left-panel">
        <SplineComponent
          scene="https://prod.spline.design/yrSXHRa01Eg4mSWv/scene.splinecode"
          onLoad={onLoad}
        />

        <div className="controls">
          <button
            className={state === 'idle' ? 'active' : ''}
            onClick={handleIdle}
          >
            💤 閒置
          </button>
          <button
            className={state === 'awake' ? 'active' : ''}
            onClick={handleAwake}
          >
            ❤️ 喚醒
          </button>
          <button
            className={state === 'reply' ? 'active' : ''}
            onClick={handleReply}
          >
            🎯 回覆
          </button>
        </div>

        {/* ✅ 新增：開始對話按鈕（左上角） */}
        {!isConnected && (
          <button
            className="start-conversation-button"
            onClick={handleStartConversation}
          >
            <span className="mic-icon">🎙️</span>
            <span className="button-text">開始語音對話</span>
          </button>
        )}

        {/* ✅ 新增：結束對話按鈕 */}
        {isConnected && (
          <button
            className="end-conversation-button"
            onClick={async () => {
              await disconnect();
              await stopRecording();
            }}
          >
            <span className="end-icon">🔴</span>
            <span className="button-text">結束對話</span>
          </button>
        )}

        {/* ✅ 顯示連接狀態 */}
        <div className="status-indicator">
          {!isConnected && '🔴 未連接'}
          {isConnected && !isPublishing && !agentState.isSpeaking && '🟡 已連接'}
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

        {/* 聊天開關按鈕 */}
        <button
          className="chat-toggle-button"
          onClick={() => setShowChat(!showChat)}
          title={showChat ? '隱藏對話記錄' : '顯示對話記錄'}
        >
          {showChat ? '💬 隱藏對話' : '💬 顯示對話'}
        </button>

        {/* 麥克風按鈕 */}
        <button
          className={`mic-button ${isRecording ? 'recording' : ''}`}
          onClick={toggleRecording}
          title={isRecording ? '隱藏麥克風視覺化' : '顯示麥克風視覺化'}
        >
          {isRecording ? '🎤 隱藏視覺化' : '🎤 顯示視覺化'}
        </button>

        {/* 音訊視覺化 - 只在錄音時顯示 */}
        {isRecording && (
          <div className="audio-visualizer-vertical">
            {[...Array(10)].map((_, index) => {
              // 從下往上計算，index 0 是最底部
              const threshold = index / 10; // 0.0, 0.1, 0.2 ... 0.9
              const isActive = audioLevel >= threshold;

              return (
                <div
                  key={index}
                  className={`audio-level-bar ${isActive ? 'active' : ''}`}
                />
              );
            })}
          </div>
        )}

        {/* 訊息框 - 顯示 Agent 最新回覆 */}
        {currentMessage && (
          <div className="message-bubble">
            <svg viewBox="0 0 520 200" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <path id="bubble-path"
                  d="M60,46
                     H165
                     l-15,-34
                     l60,34
                     H420 a24,24 0 0 1 24,24
                     V156 a24,24 0 0 1 -24,24
                     H60  a24,24 0 0 1 -24,-24
                     V70  a24,24 0 0 1 24,-24
                     Z" />

                {/* ✅ 定義遮罩矩形（使用 SVG 座標系，與 viewBox 520×200 對齊） */}
                <clipPath id="text-clip-path" clipPathUnits="userSpaceOnUse">
                  <rect x="44" y="46" width="408" height="110" rx="24" />
                </clipPath>

                <linearGradient id="gold-glass" x1="0" y1="0" x2="0" y2="1">
                  <stop stopColor="rgba(247, 233, 203, 0.75)"/>
                </linearGradient>
              </defs>

              {/* 填色（底色） */}
              <use href="#bubble-path" fill="url(#gold-glass)"/>

              {/* 外描邊（白色，製造貼紙外框感） */}
              <use href="#bubble-path"
                   fill="none"
                   stroke="#ffffff"
                   strokeWidth="16"
                   strokeLinejoin="round"
                   strokeLinecap="round"/>

              {/* 內描邊（黑色） */}
              <use href="#bubble-path"
                   fill="none"
                   stroke="#B3852F"
                   strokeWidth="6"
                   strokeLinejoin="round"
                   strokeLinecap="round"/>
            </svg>

            <div className="message-bubble__content message-bubble__clipped">
              <div className="message-bubble__scrollable" ref={messageBubbleRef}>
                {currentMessage}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 右側：聊天區 */}
      {showChat && (
        <div className="right-panel glass-panel">
          <div className="chat-header glass-subtle">
            <h2>對話記錄</h2>
          </div>

          <div className="chat-messages">
            {chatHistory.map((msg, index) => (
              <div
                key={index}
                className={`chat-message ${msg.isUser ? 'user-message' : 'ai-message'}`}
              >
                <div className={`message-bubble-glass ${msg.isUser ? 'is-user' : 'is-ai'}`}>
                  <div className="message-text">{msg.text}</div>
                  <div className="message-time">{msg.timestamp}</div>
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          <div className="chat-input-area glass-input">
            <input
              type="text"
              className="chat-input"
              placeholder="輸入訊息..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={handleKeyPress}
            />
            <button className="send-button" onClick={handleSendMessage}>
              送出
            </button>
          </div>
        </div>
      )}

      {/* 即時轉錄顯示（底部） */}
    </div>
  );
}
