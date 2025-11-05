/**
 * 垂直佈局版本 (Vertical Layout Version)
 *
 * 此頁面使用 RWD 方式實現垂直（手機）介面配置：
 * - Spline 球體與倒影整體往上移動
 * - 中央置中的「點 按 喚 醒」按鈕（稍微往上）
 * - 對話氣泡框往上調整
 * - Logo 和結束對話按鈕位置微調
 * - 對話切換按鈕和麥克風按鈕保持原位
 * - 使用 RWD 響應式設計
 */

import SplineViewerVertical from './SplineViewerVertical';

export default function VerticalLayout() {
  return (
    <main>
      <SplineViewerVertical />
    </main>
  );
}
