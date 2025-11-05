/**
 * 訊息排程器
 * 純 TypeScript 實作，處理閒置狀態的訊息輪播
 */

import type { MessageSchedulerConfig } from '../types/spline.types';

/**
 * 預設配置
 */
const DEFAULT_CONFIG: MessageSchedulerConfig = {
  minDelay: 4000,    // 4 秒
  maxDelay: 7000,    // 7 秒
  displayDuration: 4000,  // 顯示 4 秒
};

/**
 * 預設訊息列表
 */
export const DEFAULT_MESSAGES = [
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
  "記得要好好休息，保持活力喔！",
];

/**
 * 訊息排程器類別
 */
export class MessageScheduler {
  private timerId: NodeJS.Timeout | null = null;
  private messages: string[];
  private config: MessageSchedulerConfig;
  private lastIndex: number = -1;
  private isRunning: boolean = false;

  constructor(
    messages: string[] = DEFAULT_MESSAGES,
    config: Partial<MessageSchedulerConfig> = {}
  ) {
    this.messages = messages;
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * 開始排程（閒置狀態）
   */
  start(onMessage: (message: string) => void): void {
    if (this.isRunning) {
      console.warn('MessageScheduler already running');
      return;
    }

    this.isRunning = true;
    console.log('📅 MessageScheduler started');

    const scheduleNext = () => {
      if (!this.isRunning) return;

      // 隨機延遲 minDelay - maxDelay
      const delay =
        Math.random() * (this.config.maxDelay - this.config.minDelay) +
        this.config.minDelay;

      this.timerId = setTimeout(() => {
        if (!this.isRunning) return;

        // 隨機選擇一句話（避免與上次相同）
        const newIndex = this.getRandomIndex();
        this.lastIndex = newIndex;
        const message = this.messages[newIndex];

        // 顯示訊息
        onMessage(message);

        // 顯示一段時間後清空，然後排程下一次
        setTimeout(() => {
          if (!this.isRunning) return;
          onMessage(''); // 清空訊息
          scheduleNext(); // 遞迴排程下一次
        }, this.config.displayDuration);
      }, delay);
    };

    // 立即清空訊息
    onMessage('');
    // 開始排程
    scheduleNext();
  }

  /**
   * 停止排程
   */
  stop(): void {
    if (this.timerId) {
      clearTimeout(this.timerId);
      this.timerId = null;
    }
    this.isRunning = false;
    this.lastIndex = -1;
    console.log('🛑 [MessageScheduler] Stopped and reset');
  }

  /**
   * 檢查是否正在執行
   */
  isActive(): boolean {
    return this.isRunning;
  }

  /**
   * 更新訊息列表
   */
  setMessages(messages: string[]): void {
    if (messages.length === 0) {
      console.warn('Messages array cannot be empty');
      return;
    }
    this.messages = messages;
    this.lastIndex = -1; // 重置索引
  }

  /**
   * 取得隨機索引（避免與上次相同）
   */
  private getRandomIndex(): number {
    if (this.messages.length === 1) {
      return 0;
    }

    let newIndex;
    do {
      newIndex = Math.floor(Math.random() * this.messages.length);
    } while (newIndex === this.lastIndex);

    return newIndex;
  }

  /**
   * 更新配置
   */
  setConfig(config: Partial<MessageSchedulerConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * 取得當前配置
   */
  getConfig(): MessageSchedulerConfig {
    return { ...this.config };
  }

  /**
   * 清理資源
   */
  dispose(): void {
    this.stop();
    this.messages = [];
  }
}
