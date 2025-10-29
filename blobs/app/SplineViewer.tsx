/**
 * SplineViewer Component - 水平佈局版本 (Horizontal Layout Version)
 *
 * 當前配置特點：
 * - 「點 按 喚 醒」按鈕：中央置中（top: 50%, left: 50%, transform: translate(-50%, -50%)）
 * - Logo：左上角（top: 40px, left: 40px, width: 120px）
 * - 結束對話按鈕：Logo 下方（top: 80px, left: 40px, width: 120px）
 * - 對話切換按鈕：右上角，使用 SVG 圖標切換顯示/隱藏（top: 40px, right: 40px）
 * - 麥克風按鈕：右下角（bottom: 40px, right: 40px）
 * - SVG 反射陰影：銀白色漸層（240,245,250 → 220,230,240 → 200,215,230）
 * - 按鈕樣式：玻璃擬態設計（padding: 6px 16px, border-radius: 69px）
 *
 * 可通過 /horizontal 路由訪問此佈局
 */

"use client";

import { useRef, useState, useEffect } from "react";
import type { Application } from "@splinetool/runtime";
import { useLiveKit } from "./hooks/useLiveKit";

// 匯入純 TypeScript 模組
import { AnimationManager } from "./utils/animations";
import {
  AudioAnalyzer,
  createMicrophoneStream,
  stopMediaStream,
} from "./utils/audioAnalyzer";
import { ChatManager, createAIMessage } from "./utils/chatManager";
import { MessageScheduler } from "./utils/messageScheduler";
import { createConnectionConfig } from "./utils/livekitClient";

// 匯入類型
import type { AnimationState, ChatMessage } from "./types/spline.types";

const INITIAL_BUBBLE_MESSAGE =
  "HELLO 你可以直接說話問我 OR 按下按鈕開始對話";
const QUICK_PROMPTS = [
  "HELLO 你可以直接說話問我",
  "想知道廁所在哪？",
  "附近有什麼好吃的餐廳？",
  "過站要怎麼補票？？",
];

export default function SplineViewer() {
  // Spline 相關
  const [SplineComponent, setSplineComponent] = useState<any>(null);
  const [state, setState] = useState<AnimationState>("idle");
  const [sphereYOffset, setSphereYOffset] = useState<number>(0); // 追蹤球體的 Y 軸偏移量（跳動高度）
  const [sphereScale, setSphereScale] = useState<number>(1); // 追蹤球體的縮放比例（脈動大小）

  // 管理器實例（使用 ref 避免重複建立）
  const animationManagerRef = useRef<AnimationManager | null>(null);
  const audioAnalyzerRef = useRef<AudioAnalyzer | null>(null);
  const chatManagerRef = useRef<ChatManager | null>(null);
  const messageSchedulerRef = useRef<MessageScheduler | null>(null);
  const splineAppRef = useRef<Application | null>(null); // 保存 Spline Application 引用
  const scaleMonitorCleanupRef = useRef<(() => void) | null>(null); // 保存縮放監聽清理函數

  // UI 狀態
  const [currentMessage, setCurrentMessage] = useState<string>(
    INITIAL_BUBBLE_MESSAGE
  );
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState<string>("");
  const [showChat, setShowChat] = useState<boolean>(true);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [audioPermissionGranted, setAudioPermissionGranted] = useState(false);
  const [rotatingPromptIndex, setRotatingPromptIndex] = useState<number>(0);

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

  const isDefaultBubble = currentMessage === INITIAL_BUBBLE_MESSAGE;

  // 初始化 Spline Component
  useEffect(() => {
    import("@splinetool/react-spline").then((mod) => {
      setSplineComponent(() => mod.default);
    });
  }, []);

  // 輪播提示文字
  useEffect(() => {
    if (!isConnected && isDefaultBubble) {
      const interval = setInterval(() => {
        setRotatingPromptIndex((prev) => (prev + 1) % QUICK_PROMPTS.length);
      }, 3000); // 每 3 秒切換一次

      return () => clearInterval(interval);
    }
  }, [isConnected, isDefaultBubble]);

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
      scaleMonitorCleanupRef.current?.(); // 清理縮放監聽
      stopMediaStream(micStreamRef.current);
    };
  }, []);

  // Spline 載入完成
  function onLoad(spline: Application) {
    const sphere = spline.findObjectByName("Sphere");
    if (!sphere) {
      console.warn("⚠️ Sphere not found yet, waiting for scene to load...");
      return;
    }

    // 防止重複初始化
    if (animationManagerRef.current) {
      console.log("⚠️ AnimationManager already initialized, skipping...");
      return;
    }

    console.log("✅ Sphere found:", sphere.name);
    const initialY = sphere.position.y;

    // 保存 Spline Application 引用
    splineAppRef.current = spline;

    // 建立動畫管理器
    animationManagerRef.current = new AnimationManager(
      sphere,
      initialY,
      undefined // 使用預設動畫配置
    );
    animationManagerRef.current.switchTo("idle");

    // 啟動 Spline
    spline.play();

    // 禁用 Spline canvas 的滾輪縮放 - 多層攔截
    const canvas = (spline as any)._renderer?.domElement;
    const preventZoom = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      return false;
    };

    if (canvas) {
      // 在 canvas 上攔截
      canvas.addEventListener('wheel', preventZoom, { passive: false, capture: true });

      // 同時在父容器上攔截
      const container = canvas.parentElement;
      if (container) {
        container.addEventListener('wheel', preventZoom, { passive: false, capture: true });
      }

      // 禁用 Spline 的內建控制器
      if ((spline as any).controls) {
        (spline as any).controls.enabled = false;
      }
      if ((spline as any)._controls) {
        (spline as any)._controls.enabled = false;
      }

      // 保存清理函數
      const originalCleanup = scaleMonitorCleanupRef.current;
      scaleMonitorCleanupRef.current = () => {
        canvas.removeEventListener('wheel', preventZoom);
        if (container) {
          container.removeEventListener('wheel', preventZoom);
        }
        originalCleanup?.();
      };
    }

    // 開始監聽球體位置
    const cleanup = startScaleMonitoring();
    const existingCleanup = scaleMonitorCleanupRef.current;
    scaleMonitorCleanupRef.current = () => {
      cleanup();
      existingCleanup?.();
    };
  }

  // 監聽球體位置和縮放
  function startScaleMonitoring(): () => void {
    let animationFrameId: number;
    let initialSphereY: number | null = null;

    function checkPosition() {
      if (splineAppRef.current) {
        const app = splineAppRef.current as any;

        // 監聽球體 Y 位置和縮放
        const sphere = app.findObjectByName("Sphere");
        if (sphere) {
          // 記錄初始 Y 位置
          if (initialSphereY === null) {
            initialSphereY = sphere.position.y;
          }

          // 計算 Y 軸偏移量（跳動高度）
          const yOffset = sphere.position.y - initialSphereY;
          setSphereYOffset(yOffset);

          // 追蹤球體縮放比例（脈動大小）
          const scale = (sphere.scale.x + sphere.scale.y + sphere.scale.z) / 3;
          setSphereScale(scale);
        }
      }
      animationFrameId = requestAnimationFrame(checkPosition);
    }

    checkPosition();

    // 返回清理函數
    return () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
    };
  }

  // 同步 transcriptions 到 chatHistory
  useEffect(() => {
    if (transcriptions.length > 0 && chatManagerRef.current) {
      const lastTranscription = transcriptions[transcriptions.length - 1];

      const newMessage: ChatMessage = {
        text: lastTranscription.isFinal
          ? lastTranscription.text
          : lastTranscription.text + "...",
        timestamp: lastTranscription.timestamp.toLocaleTimeString("zh-TW", {
          hour: "2-digit",
          minute: "2-digit",
        }),
        isUser: lastTranscription.role === "user",
      };

      chatManagerRef.current.updateOrAddMessage(newMessage);

      // 顯示 Agent 訊息
      if (lastTranscription.role === "assistant") {
        setCurrentMessage(lastTranscription.text);
        messageBubbleRef.current?.scrollTo({
          top: messageBubbleRef.current.scrollHeight,
          behavior: "smooth",
        });
      }
    }
  }, [transcriptions]);

  // 自動滾動到最新訊息
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // 整合 Agent 狀態到動畫
  useEffect(() => {
    if (!animationManagerRef.current) return;

    console.log("🎭 Animation state check:", {
      agentSpeaking: agentState.isSpeaking,
      userSpeaking: isUserSpeaking,
      currentState: state,
    });

    // 優先級：使用者說話 > Agent 說話 > 閒置
    if (isUserSpeaking) {
      console.log("👤 User speaking - Switching to AWAKE");
      handleAwake();
    } else if (agentState.isSpeaking) {
      console.log("🤖 Agent speaking - Switching to REPLY");
      handleReply();
    } else {
      console.log("😴 Nobody speaking - Switching to IDLE");
      handleIdle();
    }
  }, [agentState.isSpeaking, isUserSpeaking]);

  // 顯示錯誤提示
  useEffect(() => {
    if (livekitError) {
      console.error("LiveKit Error:", livekitError);
    }
  }, [livekitError]);

  // 動畫控制函數
  function handleIdle() {
    setState("idle");
    animationManagerRef.current?.switchTo("idle");
    setCurrentMessage("");

    // 啟動訊息排程器
    messageSchedulerRef.current?.start((message) => {
      setCurrentMessage(message);
    });
  }

  function handleAwake() {
    setState("awake");
    animationManagerRef.current?.switchTo("awake");
    setCurrentMessage("");

    // 停止訊息排程器
    messageSchedulerRef.current?.stop();
  }

  function handleReply() {
    setState("reply");
    animationManagerRef.current?.switchTo("reply");

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
      console.error("Failed to start conversation:", error);
      alert(`連接失敗：${(error as Error).message}`);
    }
  }

  // 開始錄音
  async function startRecording() {
    if (isRecording || micStreamRef.current) {
      console.log("⚠️ Recording already in progress");
      return;
    }

    try {
      console.log("🎤 Starting microphone recording...");
      const stream = await createMicrophoneStream();
      micStreamRef.current = stream;

      // 發布到 LiveKit
      await publishMicrophone(stream);
      console.log("✅ Microphone published");

      // 初始化音訊分析器
      if (audioAnalyzerRef.current) {
        await audioAnalyzerRef.current.initialize(stream);
        audioAnalyzerRef.current.startAnalyzing((level) => {
          setAudioLevel(level);
        });
      }

      setIsRecording(true);
      setState("awake");
      animationManagerRef.current?.switchTo("awake");
    } catch (error) {
      console.error("無法存取麥克風:", error);
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
    setState("idle");
    animationManagerRef.current?.switchTo("idle");
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
  function sendUserMessage(message: string) {
    const trimmed = message.trim();
    if (!trimmed || !chatManagerRef.current) return;

    chatManagerRef.current.addUserMessage(trimmed);
    setInputText("");

    // AI 回覆（模擬）
    setTimeout(() => {
      const response = currentMessage || "我現在沒有在說話喔～";
      chatManagerRef.current?.addAIMessage(response);
    }, 1000);
  }

  function handleSendMessage() {
    sendUserMessage(inputText);
  }

  function handleQuickPrompt(prompt: string) {
    sendUserMessage(prompt);
  }

  // 處理 Enter 鍵送出
  function handleKeyPress(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      handleSendMessage();
    }
  }

  if (!SplineComponent) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
          fontSize: "20px",
          color: "#666",
        }}
      >
        Loading...
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* 左側：Spline 動畫區 */}
      <div className="left-panel">
        {/* Spline 容器 */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
          }}
        >
          {/* Spline 球體 */}
          <div
            style={{ position: "absolute", inset: 0, transform: "scale(0.78)" }}
          >
            <SplineComponent
              scene="https://prod.spline.design/yrSXHRa01Eg4mSWv/scene.splinecode"
              onLoad={onLoad}
            />
          </div>

          {/* SVG 倒影效果 - 使用 transform-origin 錨點優化 */}
          <svg
            className="glass-reflection"
            style={{
              position: "absolute",
              // 陰影固定在地面位置，與球體保持 180px 間隔
              top: "calc(50% + 180px)",
              left: "50%",
              // 固定基礎尺寸（放大三倍）
              width: `${468 * 0.8 * 3}px`,
              height: `${380 * 0.8 * 3}px`,
              pointerEvents: "none",
              // Transform-origin 設定為底部中心，讓縮放從底部錨點進行
              transformOrigin: "50% 100%",
              // 使用 transform 進行縮放和位置補償
              transform: (() => {
                // 計算縮放因子
                const scaleX = 1 + (
                  state === "reply"
                    ? sphereYOffset / 300      // 跳動：高度影響
                    : state === "awake"
                    ? (sphereScale - 1) * 2    // 脈動：縮放影響 x2
                    : 0
                );
                const scaleY = 1; // 保持 Y 方向不變，避免額外位移

                // 計算模糊補償（模糊會讓視覺邊界向外擴張）
                const currentBlur = Math.max(2, 2 + (state === "reply" ? sphereYOffset / 25 : 0));
                const cSigma = 0.75; // 校準係數
                const yComp = cSigma * currentBlur;

                return `translateX(-50%) translateY(-${yComp}px) scaleX(${scaleX}) scaleY(${scaleY})`;
              })(),
              // 透明度：根據狀態調整
              // idle: 固定 0.5（基準）
              // awake: 固定 0.5（與基準一致）
              // reply: 從基準 0.5（底部）→ 0.85（頂部，更透明）
              opacity: (() => {
                if (state === "idle" || state === "awake") {
                  return 0.5; // 閒置/喚醒：固定 0.5（基準）
                } else {
                  // 回覆：從底部 0.5（基準）往上變化到 0.85（更透明）
                  // sphereYOffset 從 0 到約 150
                  return Math.max(0.5, Math.min(0.85, 0.5 + sphereYOffset / 428.57));
                }
              })(),
              transition: "opacity 0.05s ease-out, filter 0.05s ease-out",
              // 模糊效果：只有 reply 狀態（垂直移動）才改變模糊度
              // awake 狀態（原地脈動）不改變模糊度
              filter: `blur(${Math.max(2, 2 + (state === "reply" ? sphereYOffset / 25 : 0))}px)`,
              // GPU 加速優化
              willChange: "transform, filter, opacity",
              zIndex: 10,
            }}
            viewBox="0 0 360 292"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              {/* Mask gradient - 控制可見區域 */}
              <radialGradient
                id="mask-gradient"
                cx="0"
                cy="0"
                r="1"
                gradientUnits="userSpaceOnUse"
                gradientTransform="translate(180 15.5) rotate(90) scale(374.5 345.692)"
              >
                <stop stopColor="#494949" />
                <stop offset="0.25" stopColor="#000000" stopOpacity="0" />
              </radialGradient>

              {/* 銀白色 radial gradient - 根據跳動高度調整 */}
              <radialGradient
                id="golden-reflection"
                cx="0"
                cy="0"
                r="1"
                gradientUnits="userSpaceOnUse"
                gradientTransform="translate(180 49.9846) rotate(90) scale(507.015)"
              >
                {/* 動態調整倒影顏色強度：根據狀態計算影響因子 */}
                {(() => {
                  // 計算影響因子 (0-1)
                  // reply: 球體跳得越高，顏色越淡（距離變遠）
                  // awake: 原地脈動，顏色保持清晰
                  const factor = state === "reply" ? sphereYOffset / 200 : 0;
                  return (
                    <>
                      <stop stopColor={`rgba(240, 245, 250, ${Math.max(0.3, 0.8 - factor)})`} />
                      <stop offset="0.5" stopColor={`rgba(220, 230, 240, ${Math.max(0.2, 0.5 - factor * 0.67)})`} />
                      <stop offset="1" stopColor={`rgba(200, 215, 230, ${Math.max(0.1, 0.3 - factor * 0.5)})`} />
                    </>
                  );
                })()}
              </radialGradient>
            </defs>

            <mask
              id="reflection-mask"
              style={{ maskType: "alpha" }}
              maskUnits="userSpaceOnUse"
              x="0"
              y="0"
              width="360"
              height="390"
            >
              <path d="M360 390H0V0H360V390Z" fill="url(#mask-gradient)" />
            </mask>

            <g mask="url(#reflection-mask)">
              <circle cx="180" cy="293" r="264" fill="url(#golden-reflection)" />
            </g>
          </svg>
        </div>

        <div className="controls">
          <button
            className={state === "idle" ? "active" : ""}
            onClick={handleIdle}
          >
            💤 閒置
          </button>
          <button
            className={state === "awake" ? "active" : ""}
            onClick={handleAwake}
          >
            ❤️ 喚醒
          </button>
          <button
            className={state === "reply" ? "active" : ""}
            onClick={handleReply}
          >
            🎯 回覆
          </button>
        </div>

        {/* Logo */}
        <div className="logo-container">
          <img src="/logo.png" alt="Logo" className="app-logo"  />
        </div>

        {/* 開始/結束對話按鈕 */}
        {!isConnected && (
          <button
            className="start-conversation-button"
            onClick={handleStartConversation}
          >
            <span className="mic-icon">🎙️</span>
            <span className="button-text">點 按 喚 醒</span>
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
          {!isConnected && "🔴 未連接"}
          {isConnected &&
            !isPublishing &&
            !agentState.isSpeaking &&
            "🟡 已連接"}
          {isConnected && isPublishing && !agentState.isSpeaking && "🟢 聆聽中"}
          {agentState.isSpeaking && "💬 AI 回應中"}
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
          title={showChat ? "隱藏對話記錄" : "顯示對話記錄"}
        >
          {showChat ? (
            // 隱藏對話 - X 圖標
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M6 6L18 18" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          ) : (
            // 顯示對話 - 對話泡泡圖標
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M15.2002 5V4V5ZM18.3623 5.32715L18.8164 4.4362L18.8163 4.43614L18.3623 5.32715ZM19.6729 6.6377L20.5639 6.1837L20.5638 6.18359L19.6729 6.6377ZM20 9.7998H21H20ZM20 12.2002H21H20ZM19.6729 15.3623L20.5638 15.8164L20.5639 15.8163L19.6729 15.3623ZM18.3623 16.6729L18.8163 17.5639L18.8164 17.5638L18.3623 16.6729ZM15.2002 17V18V17ZM4.76855 20.2314L4.06145 19.5243H4.06145L4.76855 20.2314ZM4 19.9141H3L3 19.915L4 19.9141ZM4 9.7998H3H4ZM4.32715 6.6377L3.4362 6.18359L3.43614 6.1837L4.32715 6.6377ZM5.6377 5.32715L5.1837 4.43614L5.18359 4.4362L5.6377 5.32715ZM8.7998 5V4V5ZM7.70711 17.2929L7 16.5858L7.70711 17.2929ZM15.2002 5V6C16.0566 6 16.639 6.00082 17.0891 6.03763C17.5276 6.07349 17.7519 6.13845 17.9083 6.21815L18.3623 5.32715L18.8163 4.43614C18.331 4.18887 17.8143 4.09026 17.2521 4.04429C16.7016 3.99927 16.0238 4 15.2002 4V5ZM18.3623 5.32715L17.9082 6.2181C18.2844 6.40981 18.5902 6.71565 18.7819 7.0918L19.6729 6.6377L20.5638 6.18359C20.1804 5.4313 19.5687 4.81963 18.8164 4.4362L18.3623 5.32715ZM19.6729 6.6377L18.7818 7.09169C18.8615 7.24811 18.9265 7.47241 18.9624 7.91089C18.9992 8.361 19 8.94335 19 9.7998H20H21C21 8.97623 21.0007 8.29838 20.9557 7.74787C20.9097 7.18573 20.8111 6.66899 20.5639 6.1837L19.6729 6.6377ZM20 9.7998H19V12.2002H20H21V9.7998H20ZM20 12.2002H19C19 13.0566 18.9992 13.639 18.9624 14.0891C18.9265 14.5276 18.8615 14.7519 18.7818 14.9083L19.6729 15.3623L20.5639 15.8163C20.8111 15.331 20.9097 14.8143 20.9557 14.2521C21.0007 13.7016 21 13.0238 21 12.2002H20ZM19.6729 15.3623L18.7819 14.9082C18.5902 15.2844 18.2844 15.5902 17.9082 15.7819L18.3623 16.6729L18.8164 17.5638C19.5687 17.1804 20.1804 16.5687 20.5638 15.8164L19.6729 15.3623ZM18.3623 16.6729L17.9083 15.7818C17.7519 15.8615 17.5276 15.9265 17.0891 15.9624C16.639 15.9992 16.0566 16 15.2002 16V17V18C16.0238 18 16.7016 18.0007 17.2521 17.9557C17.8143 17.9097 18.331 17.8111 18.8163 17.5639L18.3623 16.6729ZM15.2002 17V16H8.41421V17V18H15.2002V17ZM7.70711 17.2929L7 16.5858L4.06145 19.5243L4.76855 20.2314L5.47566 20.9386L8.41421 18L7.70711 17.2929ZM4.76855 20.2314L4.06145 19.5243C4.40614 19.1796 4.99955 19.421 5 19.9131L4 19.9141L3 19.915C3.00119 21.2083 4.56422 21.85 5.47566 20.9386L4.76855 20.2314ZM4 19.9141H5V9.7998H4H3V19.9141H4ZM4 9.7998H5C5 8.94335 5.00082 8.361 5.03763 7.91089C5.07349 7.47241 5.13845 7.24811 5.21815 7.09169L4.32715 6.6377L3.43614 6.1837C3.18887 6.66899 3.09026 7.18573 3.04429 7.74787C2.99927 8.29838 3 8.97623 3 9.7998H4ZM4.32715 6.6377L5.2181 7.0918C5.40981 6.71565 5.71565 6.40981 6.0918 6.2181L5.6377 5.32715L5.18359 4.4362C4.4313 4.81963 3.81963 5.4313 3.4362 6.18359L4.32715 6.6377ZM5.6377 5.32715L6.09169 6.21815C6.24811 6.13845 6.47241 6.07349 6.91089 6.03763C7.361 6.00082 7.94335 6 8.7998 6V5V4C7.97623 4 7.29838 3.99927 6.74787 4.04429C6.18573 4.09026 5.66899 4.18887 5.1837 4.43614L5.6377 5.32715ZM8.7998 5V6H15.2002V5V4H8.7998V5ZM8.41421 17V16C7.88378 16 7.37507 16.2107 7 16.5858L7.70711 17.2929L8.41421 18V17Z" fill="white"/>
              <path d="M8 9L16 9" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M8 13L13 13" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </button>

        {/* 麥克風按鈕 */}
        <button
          className={`mic-button ${isRecording ? "recording" : ""}`}
          onClick={toggleRecording}
          title={isRecording ? "隱藏麥克風視覺化" : "顯示麥克風視覺化"}
        >
          {isRecording ? "🎤 隱藏視覺化" : "🎤 顯示視覺化"}
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
                  className={`audio-level-bar ${isActive ? "active" : ""}`}
                />
              );
            })}
          </div>
        )}

        {/* 訊息框 - 只在連接後顯示 */}
        {isConnected && currentMessage && (
          <div className="message-bubble">
            <svg viewBox="0 0 520 300" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <path
                  id="bubble-path"
                  d="M60,46
                     H165
                     l-15,-34
                     l60,34
                     H420 a24,24 0 0 1 24,24
                     V256 a24,24 0 0 1 -24,24
                     H60  a24,24 0 0 1 -24,-24
                     V70  a24,24 0 0 1 24,-24
                     Z"
                />

                <clipPath id="text-clip-path" clipPathUnits="userSpaceOnUse">
                  <rect x="20" y="18" width="440" height="250" rx="24" />
                </clipPath>

              </defs>
            </svg>

            <div className="message-bubble__content message-bubble__clipped">
              <div
                className="message-bubble__scrollable"
                ref={messageBubbleRef}
              >
                {isDefaultBubble ? (
                  <div className="message-bubble__default">
                    <p className="message-bubble__headline">
                      {QUICK_PROMPTS[rotatingPromptIndex]}
                    </p>
                    <p className="message-bubble__divider">OR</p>
                    <div className="message-bubble__buttons">
                      {QUICK_PROMPTS.slice(1).map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          className="message-bubble__button"
                          onClick={() => handleQuickPrompt(prompt)}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  currentMessage
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 右側：聊天區 */}
      {showChat && (
        <div className="right-panel glass-panel">
          <div className="chat-header">
            <h2>對話記錄</h2>
          </div>

          <div className="chat-messages">
            {chatHistory.map((msg, index) => (
              <div
                key={index}
                className={`chat-message ${
                  msg.isUser ? "user-message" : "ai-message"
                }`}
              >
                <div
                  className={`message-bubble-glass ${
                    msg.isUser ? "is-user" : "is-ai"
                  }`}
                >
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
