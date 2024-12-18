from abc import ABC, abstractmethod

class TradingInterface(ABC):
    @abstractmethod
    def get_stock_name(self, stock_code: str) -> str:
        pass
    
    @abstractmethod
    def get_current_price(self, stock_code: str) -> int:
        pass
    
    @abstractmethod
    def open_position(self, acc_no: str, stock_code: str, qty: int) -> None:
        pass
    
    @abstractmethod
    def close_position(self, acc_no: str, stock_code: str, qty: int) -> None:
        pass
    
    @abstractmethod
    def get_latest_trade_price(self, stock_code: str):
        pass 