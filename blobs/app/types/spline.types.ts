/**
 * Spline Viewer 相關類型定義
 */

import type { Application, SPEObject } from '@splinetool/runtime';

/**
 * 動畫狀態類型
 */
export type AnimationState = 'idle' | 'awake' | 'reply';

/**
 * 聊天訊息介面
 */
export interface ChatMessage {
  text: string;
  timestamp: string;
  isUser: boolean;
}

/**
 * Spline 動畫配置
 */
export interface SplineAnimationConfig {
  idlePulse: {
    speed: number;
    amplitude: number;
  };
  awakePulse: {
    speed: number;
    heartbeatFreq: number;
  };
  replyJump: {
    speed: number;
    jumpHeight: number;
    squashY: number;
    stretchXZ: number;
    stretchY: number;
    squashXZ: number;
  };
}

/**
 * 動畫控制器介面
 */
export interface AnimationController {
  start: () => void;
  stop: () => void;
  isRunning: () => boolean;
}

/**
 * Spline 物件引用
 */
export interface SplineRefs {
  spline: Application | null;
  sphere: SPEObject | null;
  initialY: number;
}

/**
 * 音訊分析器配置
 */
export interface AudioAnalyzerConfig {
  fftSize: number;
  smoothingTimeConstant: number;
  sensitivityMultiplier: number;
}

/**
 * 音訊狀態
 */
export interface AudioState {
  level: number;
  isRecording: boolean;
  stream: MediaStream | null;
}

/**
 * LiveKit 連接配置
 */
export interface LiveKitConnectionConfig {
  url: string;
  token: string;
  userId: string;
  userName: string;
  room: string;
}

/**
 * 訊息排程器配置
 */
export interface MessageSchedulerConfig {
  minDelay: number;    // 最小延遲（毫秒）
  maxDelay: number;    // 最大延遲（毫秒）
  displayDuration: number;  // 顯示持續時間（毫秒）
}
