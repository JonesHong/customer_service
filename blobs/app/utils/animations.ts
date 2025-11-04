/**
 * Spline 動畫控制器
 * 純 TypeScript 實作，不依賴 React
 */

import type { SPEObject } from '@splinetool/runtime';
import type {
  AnimationState,
  SplineAnimationConfig,
  AnimationController,
} from '../types/spline.types';

/**
 * 預設動畫配置
 */
const DEFAULT_CONFIG: SplineAnimationConfig = {
  idlePulse: {
    speed: 0.03,
    amplitude: 0.03,
  },
  awakePulse: {
    speed: 0.08,
    heartbeatFreq: 4,
  },
  replyJump: {
    speed: 0.1,
    jumpHeight: 150,
    squashY: 0.75,
    stretchXZ: 1.3,
    stretchY: 1.08,
    squashXZ: 0.95,
  },
};

/**
 * 線性插值函數
 */
function lerp(a: number, b: number, t: number): number {
  return a * (1 - t) + b * t;
}

/**
 * 閒置動畫控制器
 */
export function createIdleAnimation(
  sphere: SPEObject,
  initialY: number,
  config: SplineAnimationConfig = DEFAULT_CONFIG
): AnimationController {
  let timerId: NodeJS.Timeout | null = null;
  let time = 0;

  return {
    start: () => {
      if (timerId) return;

      console.log('💤 閒置狀態：緩慢脈動');

      // 重置位置
      sphere.position.y = initialY;
      sphere.scale.x = 1;
      sphere.scale.y = 1;
      sphere.scale.z = 1;

      time = 0;
      timerId = setInterval(() => {
        time += config.idlePulse.speed;
        const pulse = 1.0 + Math.sin(time) * config.idlePulse.amplitude;
        sphere.scale.x = pulse;
        sphere.scale.y = pulse;
        sphere.scale.z = pulse;
      }, 50);
    },

    stop: () => {
      if (timerId) {
        clearInterval(timerId);
        timerId = null;
      }
    },

    isRunning: () => timerId !== null,
  };
}

/**
 * 喚醒動畫控制器（心跳效果）
 */
export function createAwakeAnimation(
  sphere: SPEObject,
  initialY: number,
  config: SplineAnimationConfig = DEFAULT_CONFIG
): AnimationController {
  let timerId: NodeJS.Timeout | null = null;
  let time = 0;

  return {
    start: () => {
      if (timerId) return;

      console.log('❤️ 喚醒狀態：心跳脈動');

      // 重置位置
      sphere.position.y = initialY;
      sphere.scale.x = 1;
      sphere.scale.y = 1;
      sphere.scale.z = 1;

      time = 0;
      timerId = setInterval(() => {
        time += config.awakePulse.speed;
        // 心跳效果：雙峰波形模擬真實心跳
        const heartbeat =
          Math.sin(time * config.awakePulse.heartbeatFreq) * 0.1 +
          Math.sin(time * config.awakePulse.heartbeatFreq * 2) * 0.05;
        const pulse = 1.0 + heartbeat;
        sphere.scale.x = pulse;
        sphere.scale.y = pulse;
        sphere.scale.z = pulse;
      }, 40);
    },

    stop: () => {
      if (timerId) {
        clearInterval(timerId);
        timerId = null;
      }
    },

    isRunning: () => timerId !== null,
  };
}

/**
 * 回覆動畫控制器（跳躍效果）
 */
export function createReplyAnimation(
  sphere: SPEObject,
  initialY: number,
  config: SplineAnimationConfig = DEFAULT_CONFIG
): AnimationController {
  let timerId: NodeJS.Timeout | null = null;
  let time = 0;

  return {
    start: () => {
      if (timerId) return;

      console.log('🎯 回覆狀態：上下跳動');

      time = 0;
      timerId = setInterval(() => {
        time += config.replyJump.speed;

        // 史萊姆跳躍效果：Y 軸位置變化
        const jump = Math.abs(Math.sin(time * 2.5)) * config.replyJump.jumpHeight;
        sphere.position.y = initialY + jump;

        // 真實物理彈跳變形
        const bounceProgress = jump / config.replyJump.jumpHeight; // 0 = 底部, 1 = 頂部

        // 使用 lerp 在兩種狀態之間插值
        const finalScaleY = lerp(
          config.replyJump.squashY,
          config.replyJump.stretchY,
          bounceProgress
        );
        const finalScaleXZ = lerp(
          config.replyJump.stretchXZ,
          config.replyJump.squashXZ,
          bounceProgress
        );

        sphere.scale.x = finalScaleXZ;
        sphere.scale.y = finalScaleY;
        sphere.scale.z = finalScaleXZ;
      }, 40);
    },

    stop: () => {
      if (timerId) {
        clearInterval(timerId);
        timerId = null;
      }
    },

    isRunning: () => timerId !== null,
  };
}

/**
 * 動畫管理器
 * 統一管理所有動畫狀態的切換
 */
export class AnimationManager {
  private currentController: AnimationController | null = null;
  private controllers: Map<AnimationState, AnimationController>;

  constructor(
    sphere: SPEObject,
    initialY: number,
    config: SplineAnimationConfig = DEFAULT_CONFIG
  ) {
    this.controllers = new Map([
      ['idle', createIdleAnimation(sphere, initialY, config)],
      ['awake', createAwakeAnimation(sphere, initialY, config)],
      ['reply', createReplyAnimation(sphere, initialY, config)],
    ]);
  }

  /**
   * 切換到指定動畫狀態
   */
  switchTo(state: AnimationState): void {
    // 停止當前動畫
    if (this.currentController) {
      this.currentController.stop();
    }

    // 啟動新動畫
    const controller = this.controllers.get(state);
    if (controller) {
      controller.start();
      this.currentController = controller;
    } else {
      console.warn(`Animation state "${state}" not found`);
    }
  }

  /**
   * 停止所有動畫
   */
  stopAll(): void {
    this.controllers.forEach((controller) => controller.stop());
    this.currentController = null;
  }

  /**
   * 取得當前動畫狀態
   */
  getCurrentState(): AnimationState | null {
    // 使用 Array.from 避免迭代器問題
    const entries = Array.from(this.controllers.entries());
    for (const [state, controller] of entries) {
      if (controller.isRunning()) {
        return state;
      }
    }
    return null;
  }

  /**
   * 清理資源
   */
  dispose(): void {
    this.stopAll();
    this.controllers.clear();
  }
}
