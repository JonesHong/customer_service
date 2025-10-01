"""
Services 模組 - 提供業務邏輯服務
"""

from .weather import fetch_weather
from .web_search import search_web_ddg
from .qa import (
    # 新的資料庫驅動介面
    get_qa_service,
    find_answer,
    get_all_questions,
    # 向後相容的簡單函數
    # first_visit,
    # alishan_ticket,
    # train_station_location,
    # local_food,
    # thank_you
)
from .database import get_database

__all__ = [
    'fetch_weather',
    'search_web_ddg',
    # Database
    'get_database',
    # QA service
    'get_qa_service',
    'find_answer',
    'get_all_questions',
    # QA functions (backward compatibility)
    # 'first_visit',
    # 'alishan_ticket',
    # 'train_station_location',
    # 'local_food',
    # 'thank_you'
]