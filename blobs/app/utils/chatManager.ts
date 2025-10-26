/**
 * 聊天管理器
 * 純 TypeScript 實作，處理聊天歷史和訊息邏輯
 */

import type { ChatMessage } from '../types/spline.types';

/**
 * 格式化當前時間為 HH:mm 格式
 */
export function getCurrentTime(): string {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

/**
 * 建立使用者訊息
 */
export function createUserMessage(text: string): ChatMessage {
  return {
    text,
    timestamp: getCurrentTime(),
    isUser: true,
  };
}

/**
 * 建立 AI 訊息
 */
export function createAIMessage(text: string): ChatMessage {
  return {
    text,
    timestamp: getCurrentTime(),
    isUser: false,
  };
}

/**
 * 聊天管理器類別
 */
export class ChatManager {
  private history: ChatMessage[] = [];
  private listeners: Set<(messages: ChatMessage[]) => void> = new Set();

  /**
   * 取得完整聊天歷史
   */
  getHistory(): ChatMessage[] {
    return [...this.history];
  }

  /**
   * 新增訊息
   */
  addMessage(message: ChatMessage): void {
    this.history.push(message);
    this.notifyListeners();
  }

  /**
   * 新增使用者訊息
   */
  addUserMessage(text: string): void {
    this.addMessage(createUserMessage(text));
  }

  /**
   * 新增 AI 訊息
   */
  addAIMessage(text: string): void {
    this.addMessage(createAIMessage(text));
  }

  /**
   * 更新或新增訊息（用於 LiveKit streaming）
   */
  updateOrAddMessage(message: ChatMessage): void {
    if (this.history.length > 0) {
      const lastMsg = this.history[this.history.length - 1];
      const isSameRole = lastMsg.isUser === message.isUser;
      const isInterimMessage = lastMsg.text.endsWith('...');

      // 如果是同角色且最後一則是 interim（有 "..."），取代它
      if (isSameRole && isInterimMessage) {
        this.history[this.history.length - 1] = message;
        this.notifyListeners();
        return;
      }
    }

    // 否則新增新訊息
    this.addMessage(message);
  }

  /**
   * 清空歷史
   */
  clearHistory(): void {
    this.history = [];
    this.notifyListeners();
  }

  /**
   * 取得最後一則訊息
   */
  getLastMessage(): ChatMessage | null {
    return this.history.length > 0
      ? this.history[this.history.length - 1]
      : null;
  }

  /**
   * 取得最後 n 則訊息
   */
  getLastNMessages(n: number): ChatMessage[] {
    return this.history.slice(-n);
  }

  /**
   * 訂閱歷史變更
   */
  subscribe(listener: (messages: ChatMessage[]) => void): () => void {
    this.listeners.add(listener);
    // 立即通知當前狀態
    listener([...this.history]);
    // 返回取消訂閱函數
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * 通知所有監聽者
   */
  private notifyListeners(): void {
    const messages = [...this.history];
    this.listeners.forEach((listener) => listener(messages));
  }

  /**
   * 取得訊息數量
   */
  getMessageCount(): number {
    return this.history.length;
  }

  /**
   * 篩選訊息（例如：只取得使用者訊息）
   */
  filterMessages(predicate: (msg: ChatMessage) => boolean): ChatMessage[] {
    return this.history.filter(predicate);
  }

  /**
   * 取得使用者訊息
   */
  getUserMessages(): ChatMessage[] {
    return this.filterMessages((msg) => msg.isUser);
  }

  /**
   * 取得 AI 訊息
   */
  getAIMessages(): ChatMessage[] {
    return this.filterMessages((msg) => !msg.isUser);
  }

  /**
   * 清理資源
   */
  dispose(): void {
    this.history = [];
    this.listeners.clear();
  }
}
