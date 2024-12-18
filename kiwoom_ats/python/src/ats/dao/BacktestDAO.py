from .TradingInterface import TradingInterface
import sqlite3
import datetime

class BacktestDAO(TradingInterface):
    __instance = None  # 싱글톤 인스턴스 저장소

    def __init__(self):
        self.history_db_conn = sqlite3.connect("./resources/backtest/stock_data.db")
        self.trading_db_conn = sqlite3.connect("./resources/backtest/backtest_ats.db")
        self.__latest_transaction_time = None
        self.__current_price_map = {}

    @classmethod
    def __get_instance(cls):
        return cls.__instance

    @classmethod
    def instance(cls, *args, **kargs):
        cls.__instance = cls(*args, **kargs)
        cls.instance = cls.__get_instance
        return cls.__instance

    def get_current_price(self, stock_code: str) -> int:
        cursor = self.history_db_conn.cursor()
        cursor.execute('''
            SELECT * FROM back_testing_stock_data 
            WHERE stock_code = ? ORDER BY transaction_time ASC
        ''', (stock_code,))
        rows = cursor.fetchall()

        if self.__latest_transaction_time is None:
            next_data = rows[0]
        else:
            for i, row in enumerate(rows):
                if row[3] == self.__latest_transaction_time:
                    next_data = rows[i + 1] if i < len(rows) - 1 else None
                    break

        if next_data is None:
            return -1

        current_price = abs(int(next_data[1]))
        print(f"[백테스트] {stock_code} 현재가: {current_price}")
        self.__latest_transaction_time = next_data[3]
        self.__current_price_map[stock_code] = current_price
        
        return current_price

    def open_position(self, acc_no: str, stock_code: str, qty: int) -> None:
        print(f'[백테스트] 매수 주문\n  계좌번호: {acc_no}  종목코드: {stock_code}  주문수량: {qty}')
        cursor = self.trading_db_conn.cursor()
        
        transaction_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        trade_price = self.get_current_price(stock_code)
        
        cursor.execute('''
            INSERT INTO trading_active_stocks 
            (_id, transaction_time, stock_code, trade_price, qty, acc_no)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (self._get_matching_row_count(stock_code), transaction_time, 
              stock_code, trade_price, qty, acc_no))
        
        self.trading_db_conn.commit() 