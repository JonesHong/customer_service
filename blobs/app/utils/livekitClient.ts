/**
 * LiveKit 客戶端工具函數
 * 純 TypeScript 實作，處理 token 獲取和連接配置
 */

import type { LiveKitConnectionConfig } from '../types/spline.types';

/**
 * Token API 回應介面
 */
interface TokenResponse {
  url: string;
  token: string;
  room: string;
}

/**
 * Token API 請求參數
 */
interface TokenRequest {
  user_id: string;
  user_name: string;
  room: string;
}

/**
 * 生成唯一使用者 ID
 */
export function generateUserId(): string {
  const timestamp = Date.now();
  return `user-${timestamp}`;
}

/**
 * 生成房間名稱
 */
export function generateRoomName(userId: string): string {
  const timestamp = Date.now();
  return `chiayi-user-${timestamp}`;
}

/**
 * 從後端獲取 LiveKit token
 */
export async function fetchLiveKitToken(
  userId: string,
  userName: string = '嘉義客服用戶',
  apiUrl: string = 'http://localhost:5001/get-token'
): Promise<LiveKitConnectionConfig> {
  try {
    const room = generateRoomName(userId);

    const requestBody: TokenRequest = {
      user_id: userId,
      user_name: userName,
      room,
    };

    console.log('📡 Fetching LiveKit token...', requestBody);

    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Token API error (${response.status}): ${errorText}`);
    }

    const data: TokenResponse = await response.json();

    console.log('✅ Token received:', {
      token: data.token?.substring(0, 50) + '...',
      url: data.url,
      room: data.room,
    });

    if (!data.url || !data.token) {
      throw new Error('Invalid token response: missing url or token');
    }

    return {
      url: data.url,
      token: data.token,
      userId,
      userName,
      room: data.room,
    };
  } catch (error) {
    console.error('Failed to fetch LiveKit token:', error);
    throw error;
  }
}

/**
 * 建立完整的連接配置
 */
export async function createConnectionConfig(
  userName: string = '嘉義客服用戶',
  apiUrl?: string
): Promise<LiveKitConnectionConfig> {
  const userId = generateUserId();
  return fetchLiveKitToken(userId, userName, apiUrl);
}

/**
 * 驗證連接配置
 */
export function validateConnectionConfig(
  config: Partial<LiveKitConnectionConfig>
): config is LiveKitConnectionConfig {
  return !!(
    config.url &&
    config.token &&
    config.userId &&
    config.userName &&
    config.room
  );
}

/**
 * LiveKit 錯誤類型
 */
export enum LiveKitErrorType {
  TOKEN_FETCH_FAILED = 'TOKEN_FETCH_FAILED',
  CONNECTION_FAILED = 'CONNECTION_FAILED',
  PUBLISH_FAILED = 'PUBLISH_FAILED',
  PERMISSION_DENIED = 'PERMISSION_DENIED',
  UNKNOWN = 'UNKNOWN',
}

/**
 * LiveKit 錯誤類別
 */
export class LiveKitError extends Error {
  constructor(
    public type: LiveKitErrorType,
    message: string,
    public originalError?: any
  ) {
    super(message);
    this.name = 'LiveKitError';
  }
}

/**
 * 包裝 LiveKit 錯誤
 */
export function wrapLiveKitError(error: any, type: LiveKitErrorType): LiveKitError {
  return new LiveKitError(
    type,
    error.message || 'Unknown LiveKit error',
    error
  );
}
