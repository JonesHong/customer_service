"""
日誌配置模組 - 統一管理日誌設定，避免重複輸出
"""
import logging
import sys

def setup_logging(level=logging.INFO, disable_duplicate=True):
    """
    設定日誌系統

    Args:
        level: 日誌層級
        disable_duplicate: 是否禁用可能造成重複的日誌
    """
    # 獲取 root logger
    root_logger = logging.getLogger()

    # 清除所有現有的 handler（避免重複）
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 創建 console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s %(name)s - %(message)s")
    )

    # 設定 root logger
    root_logger.addHandler(console_handler)
    root_logger.setLevel(level)

    if disable_duplicate:
        # 方案1: 將 core.* 的日誌設為不向上傳播
        core_logger = logging.getLogger("core")
        core_logger.propagate = False
        core_logger.addHandler(console_handler)
        core_logger.setLevel(level)

        # 方案2: 將 livekit.agents 的日誌層級提高（減少冗餘輸出）
        livekit_logger = logging.getLogger("livekit.agents")
        livekit_logger.setLevel(logging.WARNING)  # 只顯示警告以上的日誌

        # 方案3: 完全禁用特定的 logger
        # asyncio_logger = logging.getLogger("asyncio")
        # asyncio_logger.setLevel(logging.ERROR)

def get_logger(name):
    """
    獲取指定名稱的 logger

    Args:
        name: logger 名稱

    Returns:
        logger 實例
    """
    return logging.getLogger(name)

# 方案4: 自定義 Logger 類別，攔截重複日誌
class SingletonLogger:
    """確保每個訊息只輸出一次的 Logger"""
    _instances = {}
    _recent_logs = set()
    _max_cache = 1000  # 最多緩存的日誌數量

    @classmethod
    def get_logger(cls, name):
        if name not in cls._instances:
            logger = logging.getLogger(name)
            # 包裝原始的日誌方法
            original_info = logger.info
            original_debug = logger.debug
            original_warning = logger.warning
            original_error = logger.error

            def log_once(level_func, msg, *args, **kwargs):
                # 生成訊息的唯一標識
                msg_id = f"{name}:{msg}"
                if msg_id not in cls._recent_logs:
                    cls._recent_logs.add(msg_id)
                    # 清理過舊的緩存
                    if len(cls._recent_logs) > cls._max_cache:
                        cls._recent_logs = set(list(cls._recent_logs)[-cls._max_cache//2:])
                    return level_func(msg, *args, **kwargs)

            # 替換方法
            logger.info = lambda msg, *args, **kwargs: log_once(original_info, msg, *args, **kwargs)
            logger.debug = lambda msg, *args, **kwargs: log_once(original_debug, msg, *args, **kwargs)
            logger.warning = lambda msg, *args, **kwargs: log_once(original_warning, msg, *args, **kwargs)
            logger.error = lambda msg, *args, **kwargs: log_once(original_error, msg, *args, **kwargs)

            cls._instances[name] = logger

        return cls._instances[name]