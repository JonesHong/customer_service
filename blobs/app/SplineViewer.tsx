'use client';

import { useRef, useState, useEffect } from 'react';
import type { Application } from '@splinetool/runtime';
import { useLiveKit } from './hooks/useLiveKit';

// 匯入純 TypeScript 模組
import { AnimationManager } from './utils/animations';
import { AudioAnalyzer, createMicrophoneStream, stopMediaStream } from './utils/audioAnalyzer';
import { ChatManager, createAIMessage } from './utils/chatManager';
import { MessageScheduler } from './utils/messageScheduler';
import { createConnectionConfig } from './utils/livekitClient';

// 匯入類型
import type { AnimationState, ChatMessage } from './types/spline.types';

export default function SplineViewer() {
  // Spline 相關
  const [SplineComponent, setSplineComponent] = useState<any>(null);
  const [state, setState] = useState<AnimationState>('idle');

  // 管理器實例（使用 ref 避免重複建立）
  const animationManagerRef = useRef<AnimationManager | null>(null);
  const audioAnalyzerRef = useRef<AudioAnalyzer | null>(null);
  const chatManagerRef = useRef<ChatManager | null>(null);
  const messageSchedulerRef = useRef<MessageScheduler | null>(null);

  // UI 狀態
  const [currentMessage, setCurrentMessage] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const [showChat, setShowChat] = useState<boolean>(true);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [audioPermissionGranted, setAudioPermissionGranted] = useState(false);

  // Refs
  const messageBubbleRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const micStreamRef = useRef<MediaStream | null>(null);

  // LiveKit 整合
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
    isUserSpeaking,
  } = useLiveKit();

  // 初始化 Spline Component
  useEffect(() => {
    import('@splinetool/react-spline').then((mod) => {
      setSplineComponent(() => mod.default);
    });
  }, []);

  // 初始化管理器
  useEffect(() => {
    chatManagerRef.current = new ChatManager();
    messageSchedulerRef.current = new MessageScheduler();
    audioAnalyzerRef.current = new AudioAnalyzer();

    // 訂閱聊天歷史變更
    const unsubscribe = chatManagerRef.current.subscribe((messages) => {
      setChatHistory(messages);
    });

    return () => {
      unsubscribe();
      chatManagerRef.current?.dispose();
      messageSchedulerRef.current?.dispose();
      audioAnalyzerRef.current?.dispose();
      animationManagerRef.current?.dispose();
      stopMediaStream(micStreamRef.current);
    };
  }, []);

  // Spline 載入完成
  function onLoad(spline: Application) {
    const sphere = spline.findObjectByName('Sphere');
    if (!sphere) {
      console.warn('⚠️ Sphere not found yet, waiting for scene to load...');
      return;
    }

    // 防止重複初始化
    if (animationManagerRef.current) {
      console.log('⚠️ AnimationManager already initialized, skipping...');
      return;
    }

    console.log('✅ Sphere found:', sphere.name);
    const initialY = sphere.position.y;

    // 建立動畫管理器
    animationManagerRef.current = new AnimationManager(sphere, initialY);
    animationManagerRef.current.switchTo('idle');

    // 啟動 Spline
    spline.play();
  }

  // 同步 transcriptions 到 chatHistory
  useEffect(() => {
    if (transcriptions.length > 0 && chatManagerRef.current) {
      const lastTranscription = transcriptions[transcriptions.length - 1];

      const newMessage: ChatMessage = {
        text: lastTranscription.isFinal
          ? lastTranscription.text
          : lastTranscription.text + '...',
        timestamp: lastTranscription.timestamp.toLocaleTimeString('zh-TW', {
          hour: '2-digit',
          minute: '2-digit',
        }),
        isUser: lastTranscription.role === 'user',
      };

      chatManagerRef.current.updateOrAddMessage(newMessage);

      // 顯示 Agent 訊息
      if (lastTranscription.role === 'assistant') {
        setCurrentMessage(lastTranscription.text);
        messageBubbleRef.current?.scrollTo({
          top: messageBubbleRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }
    }
  }, [transcriptions]);

  // 自動滾動到最新訊息
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  // 整合 Agent 狀態到動畫
  useEffect(() => {
    if (!animationManagerRef.current) return;

    console.log('🎭 Animation state check:', {
      agentSpeaking: agentState.isSpeaking,
      userSpeaking: isUserSpeaking,
      currentState: state,
    });

    // 優先級：使用者說話 > Agent 說話 > 閒置
    if (isUserSpeaking) {
      console.log('👤 User speaking - Switching to AWAKE');
      handleAwake();
    } else if (agentState.isSpeaking) {
      console.log('🤖 Agent speaking - Switching to REPLY');
      handleReply();
    } else {
      console.log('😴 Nobody speaking - Switching to IDLE');
      handleIdle();
    }
  }, [agentState.isSpeaking, isUserSpeaking]);

  // 顯示錯誤提示
  useEffect(() => {
    if (livekitError) {
      console.error('LiveKit Error:', livekitError);
    }
  }, [livekitError]);

  // 動畫控制函數
  function handleIdle() {
    setState('idle');
    animationManagerRef.current?.switchTo('idle');
    setCurrentMessage('');

    // 啟動訊息排程器
    messageSchedulerRef.current?.start((message) => {
      setCurrentMessage(message);
    });
  }

  function handleAwake() {
    setState('awake');
    animationManagerRef.current?.switchTo('awake');
    setCurrentMessage('');

    // 停止訊息排程器
    messageSchedulerRef.current?.stop();
  }

  function handleReply() {
    setState('reply');
    animationManagerRef.current?.switchTo('reply');

    // 停止訊息排程器
    messageSchedulerRef.current?.stop();
  }

  // 開始對話
  async function handleStartConversation() {
    try {
      const config = await createConnectionConfig();
      await connect({ url: config.url, token: config.token });

      setAudioPermissionGranted(true);
      await startRecording();
    } catch (error) {
      console.error('Failed to start conversation:', error);
      alert(`連接失敗：${(error as Error).message}`);
    }
  }

  // 開始錄音
  async function startRecording() {
    if (isRecording || micStreamRef.current) {
      console.log('⚠️ Recording already in progress');
      return;
    }

    try {
      console.log('🎤 Starting microphone recording...');
      const stream = await createMicrophoneStream();
      micStreamRef.current = stream;

      // 發布到 LiveKit
      await publishMicrophone(stream);
      console.log('✅ Microphone published');

      // 初始化音訊分析器
      if (audioAnalyzerRef.current) {
        await audioAnalyzerRef.current.initialize(stream);
        audioAnalyzerRef.current.startAnalyzing((level) => {
          setAudioLevel(level);
        });
      }

      setIsRecording(true);
      setState('awake');
      animationManagerRef.current?.switchTo('awake');
    } catch (error) {
      console.error('無法存取麥克風:', error);
      alert((error as Error).message);
    }
  }

  // 停止錄音
  async function stopRecording() {
    await unpublishMicrophone();

    stopMediaStream(micStreamRef.current);
    micStreamRef.current = null;

    audioAnalyzerRef.current?.stopAnalyzing();

    setIsRecording(false);
    setAudioLevel(0);
    setState('idle');
    animationManagerRef.current?.switchTo('idle');
  }

  // 切換錄音狀態
  function toggleRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  // 發送訊息
  function handleSendMessage() {
    if (!inputText.trim() || !chatManagerRef.current) return;

    chatManagerRef.current.addUserMessage(inputText);
    setInputText('');

    // AI 回覆（模擬）
    setTimeout(() => {
      const response = currentMessage || "我現在沒有在說話喔～";
      chatManagerRef.current?.addAIMessage(response);
    }, 1000);
  }

  // 處理 Enter 鍵送出
  function handleKeyPress(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  }

  if (!SplineComponent) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontSize: '20px',
        color: '#666',
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

        {/* 開始/結束對話按鈕 */}
        {!isConnected && (
          <button
            className="start-conversation-button"
            onClick={handleStartConversation}
          >
            <span className="mic-icon">🎙️</span>
            <span className="button-text">開始語音對話</span>
          </button>
        )}

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

        {/* 連接狀態 */}
        <div className="status-indicator">
          {!isConnected && '🔴 未連接'}
          {isConnected && !isPublishing && !agentState.isSpeaking && '🟡 已連接'}
          {isConnected && isPublishing && !agentState.isSpeaking && '🟢 聆聽中'}
          {agentState.isSpeaking && '💬 AI 回應中'}
        </div>

        {/* 錯誤提示 */}
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

        {/* 音訊視覺化 */}
        {isRecording && (
          <div className="audio-visualizer-vertical">
            {[...Array(10)].map((_, index) => {
              const threshold = index / 10;
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

        {/* 訊息框 */}
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

                <clipPath id="text-clip-path" clipPathUnits="userSpaceOnUse">
                  <rect x="44" y="46" width="408" height="110" rx="24" />
                </clipPath>

                <linearGradient id="gold-glass" x1="0" y1="0" x2="0" y2="1">
                  <stop stopColor="rgba(247, 233, 203, 0.75)"/>
                </linearGradient>
              </defs>

              <use href="#bubble-path" fill="url(#gold-glass)"/>
              <use href="#bubble-path"
                   fill="none"
                   stroke="#ffffff"
                   strokeWidth="16"
                   strokeLinejoin="round"
                   strokeLinecap="round"/>
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
    </div>
  );
}
