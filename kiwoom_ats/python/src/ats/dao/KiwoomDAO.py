import logging
import sqlite3
import threading
from typing import Dict, List
from .TradingInterface import TradingInterface
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop
from PyQt5.QtTest import QTest
import datetime

# 설정 파서 및 예외 클래스 임포트
from python.src.ats.ConfigParser import ConfigParser
from python.src.ats.StockException import (NoSuchStockCodeError,
                                           NoSuchStockPositionError)


# KiwoomDAO 클래스 정의: 주식 데이터를 요청 및 처리하는 역할
class KiwoomDAO(TradingInterface):
    __log = logging.getLogger(__name__)  # 로깅 설정
    __thread_locker = threading.Lock()  # 스레드 동기화를 위한 락
    __instance = None  # 싱글톤 인스턴스 저장소
    __current_price_map: Dict[str, int] = dict()  # 종목별 현재가 저장소
    __tr_rq_single_data = None
    __tr_rq_multi_data = None
    __tr_data_cnt_limit = 0
    __market_status = -1  # 시장 상태 저장소
    __scr_no_counter = 2000  # 스크린 번호 초기값
    __scr_no_map: Dict[str, str] = dict()  # 종목별 스크린 번호 저장소

    def __init__(self):
        self.current_price_map = dict()
        self.trading_db_conn = self.__create_trading_db_connection()
        self.__initialize_database()

        self.kiwoom_instance = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.__register_all_slots()
        self.__tr_global_eventloop = QEventLoop()

        if int(self.kiwoom_instance.dynamicCall("GetConnectState()")) == 0:
            self.__login_eventloop = QEventLoop()
            self.kiwoom_instance.dynamicCall("CommConnect()")
            self.__login_eventloop.exec_()
        else:
            self.__log.info("이미 로그인 되어 있습니다.")

    def __create_trading_db_connection(self):
        FILE_PATH = "./resources/trading/trading.db"
        return sqlite3.connect(FILE_PATH)

    def __initialize_database(self):
        """데이터베이스 테이블 초기화"""
        cursor = self.trading_db_conn.cursor()
        
        # trading_active_stocks 테이블 생성
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
        
        # closed_trades 테이블 생성
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
        
        self.trading_db_conn.commit()

    # 종목명 반환
    def get_stock_name(self, stock_code: str) -> str:
        '''종목명 리턴

        Parameters
        ----------
        stock_code : str
            종목 코드

        Returns
        -------
        str
            종목명
        '''
        self.__thread_locker.acquire()  # 스레드 락 획득
        name = self.kiwoom_instance.dynamicCall(
            "GetMasterCodeName(QString)", stock_code)  # 종목명 요청
        self.__thread_locker.release()  # 스레드 락 해제
        if name.__len__() == 0:
            raise NoSuchStockCodeError(f"{stock_code} is not valid stock code")  # 종목명 없으면 예외 발생
        return name  # 종목명 반환

    # 계좌번호로 예수금 반환
    def get_available_balance(self, acc_no: str) -> int:
        '''예수금

        Parameters
        ----------
        acc_no : str
            계좌번호
        '''
        self.__thread_locker.acquire()  # 스레드 락 획득
        balance = int(self.__get_tr_data({
            "계좌번호": acc_no,
            "비밀번호": "",
            "상장폐지조회구분": "1",
            "비밀번호입력매체구분": "00"
        }, "주식 잔고 요청", "OPW00004", "0", "5000", ["예수금"], [])["single_data"]["예수금"])  # 예수금 요청
        self.__thread_locker.release()  # 스레드 락 해제
        return balance  # 예수금 반환

    # 종목코드로 현재가 반환
    def get_current_price(self, stock_code: str) -> int:
        if not self.__current_price_map.__contains__(stock_code):
            self.__thread_locker.acquire()
            current_price: str = self.__get_tr_data({
                "종목코드": stock_code
            }, "현재가 요청", "OPT10003", "0", self.__generate_scr_no(stock_code), ["현재가"], [], cnt=1)["single_data"]["현재가"]
            
            if current_price.__len__() == 0:
                raise RuntimeError(f"{stock_code} 종목의 현재가 받아올 수 없음")
            current_price = abs(int(current_price))

            self.__current_price_map.setdefault(stock_code, current_price)
            self.__log.info(f"{stock_code} 실시간 시세 등록")
            self.kiwoom_instance.dynamicCall(
                "SetRealReg(QString, QString, QString, QString)", self.__generate_scr_no(stock_code), stock_code, "10", "1")
            self.__thread_locker.release()

        return self.__current_price_map[stock_code]

    # 종목 상태 반환
    def get_stock_state(self, stock_code: str):
        self.__thread_locker.acquire()  # 스레드 락 획득
        val: str = self.kiwoom_instance.dynamicCall("GetMasterStockState(QString)", stock_code)  # 종목 상태 요청
        self.__thread_locker.release()  # 스레드 락 해제
        out_val = val.strip().split("|")[1:]  # 상태 정보 파싱
        return out_val  # 상태 정보 반환

    # 매수 주문
    def open_position(self, acc_no: str, stock_code: str, qty: int) -> None:
        # 키움 API를 통한 실제 매수 주문만 수행
        self.__log.info(f"매수 주문 요청\n  계좌번호: {acc_no}  종목코드: {stock_code}  주문수량: {qty}")
        self.kiwoom_instance.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)", [
                "주식 매수 주문", self.__generate_scr_no(stock_code), acc_no, 1, stock_code, qty, 0, "03", ""])

    # 매도 주문
    def close_position(self, acc_no: str, stock_code: str, qty: int) -> None:
        self.__log.info(f"매도 주문 요청\n  계좌번호: {acc_no}  종목코드: {stock_code}  주문수량: {qty}")
        # 키움 API를 통한 실제 매도 주문만 수행
        self.kiwoom_instance.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)", [
                "주식 매도 주문", self.__generate_scr_no(stock_code), acc_no, 2, stock_code, qty, 0, "03", ""])

    # TR 데이터 요청
    def __get_tr_data(self, input_value: Dict[str, str], rq_name, tr_code, perv_next: str, scr_no: str,
                      rq_single_data: List[str], rq_multi_data: List[str], cnt=0):
        '''키움 API서버에 TR 데이터를 요청한다.
        Parameters
        ----------
        input_value :
            KOA Studio 기준으로, SetInputValue에 들어갈 값

        trEnum : TrCode
            KOA Studio 기준, Tr 코드

        perv_next :
            prevNext

        scr_no :
            스크린 번호

        rq_single_data :
            받아오는 싱글데이터 목록

        rq_multi_data :
            받아오고자 하는 멀티데이터 목록

        Returns
        -------
        Dict[str, Dict[str, str]]
        '''
        self.__tr_data_cnt_limit = cnt
        self.__tr_rq_single_data = rq_single_data
        self.__tr_rq_multi_data = rq_multi_data

        self.__set_input_values(input_value)   # inputvalue 대입

        self.__comm_rq_data(rq_name, tr_code, perv_next, scr_no)
        self.__tr_global_eventloop = QEventLoop()
        self.__tr_global_eventloop.exec_()
        return self.__tr_data_temp

    def __generate_scr_no(self, stock_code: str) -> str:
        if not self.__scr_no_map.__contains__(stock_code):
            self.__scr_no_map[stock_code] = str(self.__scr_no_counter)
            self.__scr_no_counter += 1

        return self.__scr_no_map[stock_code]

    def __comm_rq_data(self, rq_name, tr_code, n_prev_next, scr_no):
        val = self.kiwoom_instance.dynamicCall(
                "CommRqData(QString, QString, QString, QString)", rq_name, tr_code, n_prev_next, scr_no)
        val = int(val)
        if val != 0:
            if val == -200:
                self.__log.fatal(f"RQ DATA [{val}]: 시세 과부하")
            elif val == -201:
                self.__log.fatal(f"RQ DATA [{val}]:  조회 문작성 에러")
            self.__log.fatal(f"RQ DATA [{val}]: 에러 발생!!!")

    def __set_input_values(self, input_value: Dict[str, str]):
        '''
        SetInputVlaue() 동적 호출 iteration 용도
        '''
        for k, v in input_value.items():
            self.kiwoom_instance.dynamicCall(
                "SetInputValue(QString, QString)", k, v)

    def __on_receive_tr_data(self, scr_no, rq_name, tr_code, prev_next):
        '''
        CommRqData 처리용 슬롯
        '''
        if tr_code == "KOA_NORMAL_BUY_KQ_ORD":
            print(scr_no, rq_name, tr_code)
            return

        # tr데이터 중, 멀티데이터의 레코드 개수를 받아옴.
        if self.__tr_data_cnt_limit == 0:
            n_record = self.kiwoom_instance.dynamicCall(
                "GetRepeatCnt(QString, QString)", tr_code, rq_name)
        else:
            n_record = min(self.kiwoom_instance.dynamicCall(
                "GetRepeatCnt(QString, QString)", tr_code, rq_name), self.__tr_data_cnt_limit)

        self.__tr_data_temp = dict()     # 이전에 저장되어 있던 임시 tr_data 삭제.
        self.__tr_data_temp["single_data"] = dict()     # empty dict 선언
        for s_data in self.__tr_rq_single_data:
            self.__tr_data_temp["single_data"][s_data] = self.kiwoom_instance.dynamicCall(
                "GetCommData(QString, QString, int, QString)", tr_code, rq_name, 0, s_data).strip()

        self.__tr_data_temp["multi_data"] = list()
        for i in range(n_record):
            m_data_dict_temp = dict()   # 멀티데이터에서 레코드 하나에 담길 딕셔너리 선언
            for m_data in self.__tr_rq_multi_data:
                m_data_dict_temp[m_data] = self.kiwoom_instance.dynamicCall(
                    "GetCommData(QString, QString, int, QString)", tr_code, rq_name, i, m_data).strip()
            self.__tr_data_temp["multi_data"].append(m_data_dict_temp)
        self.__tr_global_eventloop.exit()
    # 키움 OpenAPI 연결 시 호출되는 슬롯
    def __on_event_connect_slot(self, err_code):
        if err_code == 0:  # 연결 성공
            self.__log.info("로그인 성공")
        else:  # 연결 실패
            self.__log.info("로그인 실패")

        # 서버 종류 확인 (모의투자/실거래)
        if self.kiwoom_instance.dynamicCall("GetLoginInfo(\"GetServerGubun\")") == "1":
            self.__log.info("모의투자 서버 접속")
        else:
            self.__log.info("실거래 서버 접속")

        self.__login_eventloop.exit()  # 로그인 이벤트 루프 종료

    # 메시지 수신 시 호출되는 슬롯
    def __on_receive_msg(self, scr_no, rq_name, tr_code, msg):
        self.__log.info(f"{rq_name}: {msg}")  # 메시지 로그 출력

    # 실시간 데이터 수신 시 호출되는 슬롯
    def __on_receive_real_data(self, stock_code, real_type, real_data):
        if real_type == "주식체결":  # 실시간 주식 체결 데이터
            self.__current_price_map[stock_code] = abs(int(self.kiwoom_instance.dynamicCall(
                "GetCommRealData(QString, int)", stock_code, 10)))  # 현재가 업데이트
        elif real_type == "장시작시간":  # 장 시작 시간
            self.__market_status = int(self.kiwoom_instance.dynamicCall(
                "GetCommRealData(QString, int)", stock_code, 215))  # 시장 상태 업데이트
            self.__log.info(f"market status: {self.__market_status}")
            if self.__market_status == 8:  # 장 종료 시
                self.__log.info("장 종료")

    # 체결 데이터 수신 시 호출되는 슬롯
    def __on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        acc_no = self.kiwoom_instance.dynamicCall("GetChejanData(9201)")  # 계좌번호 수신
        stock_code = self.kiwoom_instance.dynamicCall("GetChejanData(9001)")[1:].strip()  # 종목코드 수신
        trade_price = abs(int(self.kiwoom_instance.dynamicCall("GetChejanData(910)")))  # 체결가격
        qty = abs(int(self.kiwoom_instance.dynamicCall("GetChejanData(911)")))  # 체결량
        order_type = self.kiwoom_instance.dynamicCall("GetChejanData(905)").strip()  # 주문구분
        trade_type = self.kiwoom_instance.dynamicCall("GetChejanData(212)").strip()

        if gubun == "1":  # 주문 체결 완료
            cursor = self.trading_db_conn.cursor()
            transaction_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if trade_type == "2":  # 매수
                try:
                    cursor.execute('''
                        INSERT INTO trading_active_stocks 
                        (_id, transaction_time, stock_code, trade_price, qty, acc_no)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.__get_next_trade_id(), transaction_time, stock_code, trade_price, qty, acc_no))
                    self.trading_db_conn.commit()
                    self.__log.info(f"매수 체결 완료: 계좌번호: {acc_no}, 종목코드: {stock_code}, 체결가격: {trade_price}, 체결수량: {qty}")
                except Exception as e:
                    self.trading_db_conn.rollback()
                    self.__log.error(f"매수 처리 중 오류 발생: {e}")

            elif trade_type == "1":  # 매도
                try:
                    cursor.execute('''
                        SELECT * FROM trading_active_stocks 
                        WHERE stock_code = ? AND acc_no = ? 
                        ORDER BY _id DESC LIMIT 1
                    ''', (stock_code, acc_no))
                    buy_trade = cursor.fetchone()

                    if buy_trade:
                        buy_price = buy_trade[3] * buy_trade[4]
                        sell_price = trade_price * qty
                        profit = (sell_price - buy_price) * (1 - 0.015)

                        cursor.execute('''
                            INSERT INTO closed_trades 
                            (_id, transaction_time, stock_code, trade_price, qty, acc_no, profit)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (buy_trade[0], transaction_time, stock_code, trade_price, qty, acc_no, profit))

                        cursor.execute('DELETE FROM trading_active_stocks WHERE _id = ?', (buy_trade[0],))
                        self.trading_db_conn.commit()
                        self.__log.info(f"매도 체결 완료: 계좌번호: {acc_no}, 종목코드: {stock_code}, 체결가격: {trade_price}, 체결수량: {qty}, 수익: {profit}")
                    else:
                        self.__log.warning(f"매도 처리 실패: 활성 거래를 찾을 수 없음 (종목코드: {stock_code}, 계좌번호: {acc_no})")
                except Exception as e:
                    self.trading_db_conn.rollback()
                    self.__log.error(f"매도 처리 중 오류 발생: {e}")
        elif gubun == "0":
            self.__log.info(f"체결 데이터 수신: 계좌번호: {acc_no}, 종목코드: {stock_code}, 체결가격: {trade_price}, 체결수량: {qty}, 주문구분: {order_type}, 체결구분: {trade_type}")

    # 모든 슬롯을 등록하는 메서드
    def __register_all_slots(self):
        self.kiwoom_instance.OnEventConnect.connect(
            self.__on_event_connect_slot)  # 이벤트 연결 슬롯
        self.kiwoom_instance.OnReceiveRealData.connect(
            self.__on_receive_real_data)  # 실시간 데이터 수신 슬롯
        self.kiwoom_instance.OnReceiveTrData.connect(self.__on_receive_tr_data)  # TR 데이터 수신 슬롯
        self.kiwoom_instance.OnReceiveMsg.connect(self.__on_receive_msg)  # 메시지 수신 슬롯
        self.kiwoom_instance.OnReceiveChejanData.connect(
            self.__on_receive_chejan_data)  # 체결 데이터 수신 슬롯

    def get_latest_trade_price(self, stock_code: str):
        cursor = self.trading_db_conn.cursor()
        cursor.execute('''
            SELECT trade_price FROM trading_active_stocks 
            WHERE stock_code = ? 
            ORDER BY transaction_time DESC LIMIT 1
        ''', (stock_code,))
        result = cursor.fetchone()
        return result[0] if result else None

    def __get_next_trade_id(self) -> int:
        cursor = self.trading_db_conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM (
                SELECT _id FROM trading_active_stocks
                UNION ALL
                SELECT _id FROM closed_trades
            )
        ''')
        return cursor.fetchone()[0] + 1
