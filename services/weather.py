
import logging
from urllib.parse import quote

from utils.http_client import create_http_session


# 設定日誌
weather_logger = logging.getLogger("core.weather")



def fetch_weather(city: str, timeout: float = 5.0) -> str:
    """
    取得指定城市的天氣資訊 (無狀態函數)

    Args:
        city: 城市名稱
        timeout: 請求超時時間（秒）

    Returns:
        天氣資訊字串或錯誤訊息
    """
    if not city or not city.strip():
        return "請提供城市名稱。"

    session = create_http_session()
    city_quoted = quote(city, safe="")

    # 主要使用 HTTPS，HTTP 作為備援
    urls = [
        f"https://wttr.in/{city_quoted}?format=3",
        f"http://wttr.in/{city_quoted}?format=3",  # 備援
    ]

    for url in urls:
        try:
            response = session.get(url, timeout=timeout)
            if response.ok and response.text.strip():
                weather_info = response.text.strip()
                weather_logger.info(f"Weather for {city}: {weather_info}")
                return weather_info
            else:
                weather_logger.warning(f"wttr.in bad response ({response.status_code}): {url}")
        except Exception as e:
            weather_logger.exception(f"Error retrieving weather for {city} via {url}: {e}")

    # 最終備援訊息
    return f"目前無法取得 {city} 的天氣（連線不穩或服務繁忙）。請稍後再試。"

