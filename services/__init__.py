"""
Services 模組 - 提供業務邏輯服務
"""

from .weather import fetch_weather
from .web_search import search_web_ddg
from .qa import (
    first_visit,
    alishan_ticket,
    train_station_location,
    local_food,
    thank_you,
    opening_greeting,
    general_help,
    goodbye
)

__all__ = [
    'fetch_weather',
    'search_web_ddg',
    # QA functions
    'first_visit',
    'alishan_ticket',
    'train_station_location',
    'local_food',
    'thank_you',
    'opening_greeting',
    'general_help',
    'goodbye',
]