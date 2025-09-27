"""
Services 模組 - 提供業務邏輯服務
"""

from .weather import fetch_weather
from .web_search import search_web_ddg

__all__ = [
    'fetch_weather',
    'search_web_ddg',
]