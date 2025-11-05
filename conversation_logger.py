"""
對話日誌記錄器
管理每次對話的 .log 檔案，記錄使用者與 AI agent 的對話內容
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class ConversationLogger:
    """對話日誌記錄器 - 為每次對話創建獨立的 .log 檔案"""

    def __init__(self, logs_dir: str = "logs"):
        """
        初始化對話日誌記錄器

        Args:
            logs_dir: 日誌檔案存放目錄，預設為 "logs"
        """
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

        self.log_file: Optional[Path] = None
        self.file_handler: Optional[logging.FileHandler] = None
        self.logger: Optional[logging.Logger] = None
        self.room_id: Optional[str] = None

    def start_conversation(self, room_id: str) -> str:
        """
        開始新對話，創建新的日誌檔案

        Args:
            room_id: LiveKit 房間 ID

        Returns:
            日誌檔案路徑
        """
        # 生成檔案名稱：YYYYMMdd-HHmmss-<roomid>.log
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{room_id}.log"
        self.log_file = self.logs_dir / filename

        # 創建專屬的 logger
        self.room_id = room_id
        logger_name = f"conversation.{room_id}.{timestamp}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

        # 清除舊的 handlers（避免重複）
        self.logger.handlers.clear()

        # 創建檔案 handler
        self.file_handler = logging.FileHandler(
            self.log_file,
            encoding='utf-8',
            mode='w'  # 新對話使用覆寫模式
        )
        self.file_handler.setLevel(logging.INFO)

        # 設定格式（只記錄時間和訊息，不需要 logger 名稱）
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        self.file_handler.setFormatter(formatter)

        self.logger.addHandler(self.file_handler)

        # 記錄對話開始
        self.logger.info("=" * 80)
        self.logger.info(f"對話開始 | Room ID: {room_id}")
        self.logger.info("=" * 80)

        return str(self.log_file)

    def log_user_message(self, message: str, participant_id: str = "user"):
        """
        記錄使用者訊息

        Args:
            message: 使用者說的話
            participant_id: 參與者 ID（可選）
        """
        if not self.logger:
            return

        self.logger.info(f"[USER: {participant_id}] {message}")

    def log_agent_message(self, message: str):
        """
        記錄 Agent 訊息

        Args:
            message: Agent 說的話
        """
        if not self.logger:
            return

        self.logger.info(f"[AGENT] {message}")

    def log_system_event(self, event: str):
        """
        記錄系統事件（例如：開始說話、停止說話等）

        Args:
            event: 事件描述
        """
        if not self.logger:
            return

        self.logger.info(f"[SYSTEM] {event}")

    def log_tool_call(self, tool_name: str, args: dict, result: str):
        """
        記錄工具調用

        Args:
            tool_name: 工具名稱
            args: 工具參數
            result: 工具執行結果
        """
        if not self.logger:
            return

        self.logger.info(f"[TOOL] {tool_name}")
        self.logger.info(f"  參數: {args}")
        self.logger.info(f"  結果: {result[:200]}...")  # 只記錄前 200 字元

    def end_conversation(self):
        """
        結束對話，關閉日誌檔案
        """
        if not self.logger:
            return

        self.logger.info("=" * 80)
        self.logger.info(f"對話結束 | Room ID: {self.room_id}")
        self.logger.info("=" * 80)

        # 關閉檔案 handler
        if self.file_handler:
            self.file_handler.close()
            self.logger.removeHandler(self.file_handler)
            self.file_handler = None

        # 清空狀態
        self.logger = None
        self.log_file = None
        self.room_id = None

    def get_current_log_file(self) -> Optional[str]:
        """
        取得當前日誌檔案路徑

        Returns:
            日誌檔案路徑，如果沒有活動對話則返回 None
        """
        return str(self.log_file) if self.log_file else None

    def is_active(self) -> bool:
        """
        檢查是否有活動的對話日誌

        Returns:
            True 如果有活動的對話日誌，否則 False
        """
        return self.logger is not None


# 全局單例（每個 agent 實例共用）
_conversation_logger: Optional[ConversationLogger] = None


def get_conversation_logger() -> ConversationLogger:
    """
    取得全局對話日誌記錄器實例

    Returns:
        ConversationLogger 實例
    """
    global _conversation_logger
    if _conversation_logger is None:
        _conversation_logger = ConversationLogger()
    return _conversation_logger
