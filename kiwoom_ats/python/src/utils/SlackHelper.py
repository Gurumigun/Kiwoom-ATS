import requests
import json
import logging
from typing import Optional

class SlackHelper:
    __instance = None
    __log = logging.getLogger(__name__)

    def __init__(self, webhook_url: str = None):
        """
        Args:
            webhook_url (str, optional): Slack Webhook URL. 
                환경변수 SLACK_WEBHOOK_URL이 설정되어 있다면 생략 가능
        """
        self.webhook_url = webhook_url or os.environ.get('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            self.__log.warning("Slack webhook URL이 설정되지 않았습니다. 메시지 전송이 불가능합니다.")

    @classmethod
    def __get_instance(cls):
        return cls.__instance

    @classmethod
    def instance(cls, *args, **kwargs):
        cls.__instance = cls(*args, **kwargs)
        cls.instance = cls.__get_instance
        return cls.__instance

    def send_message(self, text: str, channel: Optional[str] = None) -> bool:
        """Slack으로 메시지를 전송합니다.

        Args:
            text (str): 전송할 메시지
            channel (str, optional): 메시지를 전송할 ��널. Webhook 설정의 기본 채널이 사용됨

        Returns:
            bool: 전송 성공 여부
        """
        if not self.webhook_url:
            self.__log.warning("Slack webhook URL이 설정되지 않아 메시지를 전송할 수 없습니다.")
            return False

        payload = {
            "text": text
        }
        if channel:
            payload["channel"] = channel

        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code != 200:
                self.__log.error(f"Slack 메시지 전송 실패: {response.status_code} - {response.text}")
                return False
                
            return True
        except Exception as e:
            self.__log.error(f"Slack 메시지 전송 중 오류 발생: {str(e)}")
            return False

    def send_trade_notification(self, trade_type: str, stock_name: str, stock_code: str, 
                              price: int, qty: int, profit: Optional[float] = None) -> bool:
        """매매 알림을 전송합니다.

        Args:
            trade_type (str): 거래 유형 ("매수" 또는 "매도")
            stock_name (str): 종목명
            stock_code (str): 종목코드
            price (int): 거래가격
            qty (int): 거래수량
            profit (float, optional): 수익금 (매도 시에만 사용)

        Returns:
            bool: 전송 성공 여부
        """
        emoji = "🔵" if trade_type == "매수" else "🔴"
        message = f"{emoji} {trade_type} 체결\n"
        message += f"• 종목: {stock_name}({stock_code})\n"
        message += f"• 가격: {price:,}원\n"
        message += f"• 수량: {qty:,}주\n"
        
        if profit is not None:
            profit_emoji = "💰" if profit > 0 else "💸"
            message += f"• 수익: {profit_emoji} {profit:,.0f}원"

        return self.send_message(message)

    def send_error_notification(self, error_msg: str, stock_info: Optional[str] = None) -> bool:
        """에러 알림을 전송합니다.

        Args:
            error_msg (str): 에러 메시지
            stock_info (str, optional): 종목 정보

        Returns:
            bool: 전송 성공 여부
        """
        message = "⚠️ 오류 발생\n"
        if stock_info:
            message += f"• 종목: {stock_info}\n"
        message += f"• 내용: {error_msg}"
        
        return self.send_message(message) 