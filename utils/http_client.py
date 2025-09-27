"""
HTTP 客戶端工具模組
提供帶有重試機制的 HTTP Session 建立
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_http_session() -> requests.Session:
    """
    建立帶有重試機制的 HTTP Session

    Returns:
        設定好的 requests.Session 物件
    """
    retry = Retry(
        total=3,                # 最多重試 3 次
        backoff_factor=0.5,     # 0.5, 1.0, 2.0 秒遞增
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Friday-MCP/1.0 (+https://example.local)"
    })
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session