/**
 * 音訊分析器
 * 純 TypeScript 實作，處理音訊視覺化和音量檢測
 */

import type { AudioAnalyzerConfig } from '../types/spline.types';

/**
 * 預設音訊分析器配置
 */
const DEFAULT_CONFIG: AudioAnalyzerConfig = {
  fftSize: 2048,
  smoothingTimeConstant: 0.8,
  sensitivityMultiplier: 6,
};

/**
 * 音訊分析器類別
 */
export class AudioAnalyzer {
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private animationFrameId: number | null = null;
  private config: AudioAnalyzerConfig;

  constructor(config: Partial<AudioAnalyzerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * 初始化音訊分析器
   */
  async initialize(stream: MediaStream): Promise<void> {
    if (this.audioContext) {
      console.warn('AudioAnalyzer already initialized');
      return;
    }

    try {
      this.audioContext = new AudioContext();
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = this.config.fftSize;
      this.analyser.smoothingTimeConstant = this.config.smoothingTimeConstant;

      this.source = this.audioContext.createMediaStreamSource(stream);
      this.source.connect(this.analyser);

      console.log('✅ AudioAnalyzer initialized');
    } catch (error) {
      console.error('Failed to initialize AudioAnalyzer:', error);
      throw error;
    }
  }

  /**
   * 開始分析音訊（需提供回調函數）
   */
  startAnalyzing(onLevelUpdate: (level: number) => void): void {
    if (!this.analyser) {
      console.warn('AudioAnalyzer not initialized');
      return;
    }

    if (this.animationFrameId !== null) {
      console.warn('AudioAnalyzer already analyzing');
      return;
    }

    const analyze = () => {
      if (!this.analyser) return;

      const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
      this.analyser.getByteFrequencyData(dataArray);

      // 計算平均音量（頻域）
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;

      // 正規化到 0-1，提高靈敏度
      const normalizedLevel = Math.min(
        (average / 255) * this.config.sensitivityMultiplier,
        1
      );

      onLevelUpdate(normalizedLevel);

      this.animationFrameId = requestAnimationFrame(analyze);
    };

    analyze();
    console.log('🎵 AudioAnalyzer started analyzing');
  }

  /**
   * 停止分析
   */
  stopAnalyzing(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
      console.log('🛑 AudioAnalyzer stopped analyzing');
    }
  }

  /**
   * 取得當前音量（一次性查詢）
   */
  getCurrentLevel(): number {
    if (!this.analyser) return 0;

    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const average = sum / dataArray.length;

    return Math.min((average / 255) * this.config.sensitivityMultiplier, 1);
  }

  /**
   * 是否正在分析
   */
  isAnalyzing(): boolean {
    return this.animationFrameId !== null;
  }

  /**
   * 清理資源
   */
  dispose(): void {
    this.stopAnalyzing();

    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.analyser = null;
    console.log('🧹 AudioAnalyzer disposed');
  }
}

/**
 * 請求麥克風權限並建立音訊串流
 */
export async function createMicrophoneStream(
  constraints: MediaStreamConstraints = {
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      sampleRate: 48000,
      channelCount: 1,
    },
  }
): Promise<MediaStream> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    console.log('🎤 Microphone stream created');
    return stream;
  } catch (error: any) {
    console.error('Failed to create microphone stream:', error);

    // 提供更友善的錯誤訊息
    if (error.name === 'NotAllowedError') {
      throw new Error('請允許麥克風權限以開始對話');
    } else if (error.name === 'NotFoundError') {
      throw new Error('找不到麥克風設備，請檢查設備連接');
    } else {
      throw new Error(`麥克風初始化失敗：${error.message}`);
    }
  }
}

/**
 * 停止音訊串流
 */
export function stopMediaStream(stream: MediaStream | null): void {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    console.log('🛑 Media stream stopped');
  }
}
