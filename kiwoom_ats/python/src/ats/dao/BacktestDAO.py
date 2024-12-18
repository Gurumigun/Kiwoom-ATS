from .TradingInterface import TradingInterface
import sqlite3
import datetime
import logging
import threading

class BacktestDAO(TradingInterface):
    __instance = None
    logger = logging.getLogger(__name__)
    __local = threading.local()  # 스레드별 로컬 저장소

    def __init__(self):
        self.logger.info("BacktestDAO 초기화")
        self.__initialize_database_connections()

    def __initialize_database_connections(self):
        """현재 스레드의 데이터베이스 연결 초기화"""
        if not hasattr(self.__local, 'history_db_conn'):
            self.__local.history_db_conn = sqlite3.connect("./resources/backtest/stock_data.db")
            self.__local.trading_db_conn = sqlite3.connect("./resources/backtest/backtest_ats.db")
            self.__local.latest_transaction_time = None
            self.__local.current_price_map = {}
            self.__initialize_database()

    def __initialize_database(self):
        """데이터베이스 테이블 초기화"""
        cursor = self.__local.trading_db_conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_active_stocks (
                _id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_time DATETIME NOT NULL,
                stock_code TEXT NOT NULL,
                trade_price REAL NOT NULL,
                qty INTEGER NOT NULL,
                acc_no TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS closed_trades (
                _id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_time DATETIME NOT NULL,
                stock_code TEXT NOT NULL,
                trade_price REAL NOT NULL,
                qty INTEGER NOT NULL,
                acc_no TEXT NOT NULL,
                profit REAL NOT NULL
            )
        ''')
        self.__local.trading_db_conn.commit()

    @classmethod
    def __get_instance(cls):
        return cls.__instance

    @classmethod
    def instance(cls, *args, **kargs):
        cls.__instance = cls(*args, **kargs)
        cls.instance = cls.__get_instance
        return cls.__instance

    def get_stock_name(self, stock_code: str) -> str:
        """백테스팅용 종목명 조회"""
        cursor = self.__local.history_db_conn.cursor()
        cursor.execute('''
            SELECT DISTINCT stock_name FROM back_testing_stock_data 
            WHERE stock_code = ? LIMIT 1
        ''', (stock_code,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return f"종목_{stock_code}"  # 백테스팅에서는 실제 종목명이 중요하지 않음

    def get_latest_trade_price(self, stock_code: str):
        self.__initialize_database_connections()  # 현재 스레드의 연결 확인
        cursor = self.__local.trading_db_conn.cursor()
        cursor.execute('''
            SELECT trade_price FROM trading_active_stocks 
            WHERE stock_code = ? 
            ORDER BY transaction_time DESC LIMIT 1
        ''', (stock_code,))
        result = cursor.fetchone()
        return result[0] if result else None

    def get_current_price(self, stock_code: str) -> int:
        self.__initialize_database_connections()  # 현재 스레드의 연결 확인
        cursor = self.__local.history_db_conn.cursor()
        cursor.execute('''
            SELECT * FROM back_testing_stock_data 
            WHERE stock_code = ? ORDER BY transaction_time ASC
        ''', (stock_code,))
        rows = cursor.fetchall()

        if self.__local.latest_transaction_time is None:
            next_data = rows[0]
        else:
            for i, row in enumerate(rows):
                if row[3] == self.__local.latest_transaction_time:
                    next_data = rows[i + 1] if i < len(rows) - 1 else None
                    break

        if next_data is None:
            print(f"[백테스트] {stock_code} 모든 데이터 처리 완료")
            return -1  # 종료 신호

        current_price = abs(int(next_data[1]))
        print(f"[백테스트] {stock_code} 현재가: {current_price}")
        self.__local.latest_transaction_time = next_data[3]
        self.__local.current_price_map[stock_code] = current_price
        
        return current_price
    
    def close_position(self, acc_no: str, stock_code: str, qty: int) -> None:
        self.__initialize_database_connections()
        """백테스팅용 매도 처리"""
        print(f"[백테스트] 매도 주문\n  계좌번호: {acc_no}  종목코드: {stock_code}  주문수량: {qty}")
        cursor = self.__local.trading_db_conn.cursor()
        
        # 매수 기록 찾기
        cursor.execute('''
            SELECT * FROM trading_active_stocks 
            WHERE stock_code = ? AND acc_no = ? 
            ORDER BY _id DESC LIMIT 1
        ''', (stock_code, acc_no))
        buy_trade = cursor.fetchone()
        
        if buy_trade:
            current_price = self.get_current_price(stock_code)
            buy_price = buy_trade[3] * buy_trade[4]  # trade_price * qty
            sell_price = current_price * qty
            profit = (sell_price - buy_price) * (1 - 0.015)  # 수수료 1.5% 고려
            
            # 매도 기록 저장
            cursor.execute('''
                INSERT INTO closed_trades 
                (_id, transaction_time, stock_code, trade_price, qty, acc_no, profit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (buy_trade[0], datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  stock_code, current_price, qty, acc_no, profit))
            
            # 활성 거래에서 제거
            cursor.execute('DELETE FROM trading_active_stocks WHERE _id = ?', (buy_trade[0],))
            self.__local.trading_db_conn.commit()


    def open_position(self, acc_no: str, stock_code: str, qty: int) -> None:
        self.__initialize_database_connections()
        print(f'[백테스트] 매수 주문\n  계좌번호: {acc_no}  종목코드: {stock_code}  주문수량: {qty}')
        cursor = self.__local.trading_db_conn.cursor()
        
        transaction_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        trade_price = self.get_current_price(stock_code)
        
        cursor.execute('''
            INSERT INTO trading_active_stocks 
            (_id, transaction_time, stock_code, trade_price, qty, acc_no)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (self.__get_next_trade_id(), transaction_time, 
              stock_code, trade_price, qty, acc_no))
        
        self.__local.trading_db_conn.commit() 

    def __get_next_trade_id(self) -> int:
        """다음 거래 ID를 생성합니다."""
        cursor = self.__local.trading_db_conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM (
                SELECT _id FROM trading_active_stocks
                UNION ALL
                SELECT _id FROM closed_trades
            )
        ''')
        return cursor.fetchone()[0] + 1