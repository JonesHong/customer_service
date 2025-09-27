"""
QA 服務模組 - 提供嘉義旅遊常見問答
根據 docs/qa.json 內容提供預設回答
"""


def first_visit():
    """
    問題: 這是我第一次來嘉義，可以告訴我有什麼特別值得看的嗎？

    Returns:
        str: 嘉義景點推薦
    """
    return "歡迎來到嘉義！最有名的景點是阿里山，特別是日出和森林小火車。"


def alishan_ticket():
    """
    問題: 阿里山森林鐵路聽起來好棒！我要怎麼買票呢？

    Returns:
        str: 阿里山森林鐵路購票資訊
    """
    return "你可以直接在這裡的櫃檯買票，或者提前在網路上預訂。購票時可能需要護照。"


def train_station_location():
    """
    問題: 搭去阿里山的火車站就在附近嗎？

    Returns:
        str: 阿里山火車站位置說明
    """
    return "火車就是從這個車站出發的，只要跟著「阿里山森林鐵路」的指示牌就行。"


def local_food():
    """
    問題: 我在哪裡可以嘗到在地的美食呢？

    Returns:
        str: 嘉義在地美食推薦
    """
    return "我推薦火雞肉飯和砂鍋魚頭——在車站附近就有很多餐廳。"


def thank_you():
    """
    問題: 謝謝你！

    Returns:
        str: 感謝回應
    """
    return "祝你有個美好的旅程，如果需要更多幫助，隨時可以再來詢問！"


# 額外的通用問答函數

def opening_greeting():
    """
    開場問候

    Returns:
        str: 歡迎詞
    """
    return "歡迎來到嘉義旅遊服務中心！我是您的服務助理，有什麼可以幫助您的嗎？"


def general_help():
    """
    一般協助

    Returns:
        str: 提供協助的選項
    """
    return "我可以為您介紹嘉義的景點、美食、交通，或是協助您安排阿里山的行程。請問您對什麼有興趣？"


def goodbye():
    """
    道別

    Returns:
        str: 道別詞
    """
    return "祝您在嘉義有個愉快的旅程！再見！"