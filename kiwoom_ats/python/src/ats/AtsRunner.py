import logging
import threading
import time

from python.src.ats.ConfigParser import ConfigParser
from python.src.ats.dao.KiwoomDAO import KiwoomDAO
from python.src.ats.RunnerLocker import RunnerLocker
from python.src.ats.StockException import NoSuchStockPositionError
from python.src.ats.dao.BacktestDAO import BacktestDAO


class AtsRunner(threading.Thread):
    config = None
    state = -1
    run_flag = True
    current_price: int
    is_back_testing_mode = False
    logger = logging.getLogger(__name__)

    def __init__(self, config):
        super().__init__()
        self.logger = logging.getLogger(f"{__name__}.{config['stock_code']}")
        self.logger.info(f"AtsRunner 초기화 - {config['stock_name']}({config['stock_code']})")
        self.config = config
        self.is_back_testing_mode = ConfigParser.instance().is_back_testing_mode()
        
        # 백테스팅/실거래 DAO 선택
        if self.is_back_testing_mode:
            self.trading_dao = BacktestDAO.instance()
        else:
            self.trading_dao = KiwoomDAO.instance()
            if "거래정지" in self.trading_dao.get_stock_state(self.config["stock_code"]):
                self.logger.info(self.__format_log_msg("거래정지 되었습니다."))

        if not self.is_back_testing_mode:
            if config.__contains__("state"):
                self.logger.info(self.__format_log_msg(f"이전 거래 데이터 불러왔습니다. state: {config['state']}"))
                self.state = config["state"]
                RunnerLocker.instance().open_locker()

        self.refresh_all_data()
        self.logger.info(self.__format_log_msg("실행 준비 완료"))

    def run(self):
        self.logger.info(self.__format_log_msg("스레드 가동"))
        try:
            self.processing_loop()
        except Exception as e:
            self.logger.exception(self.__format_log_msg("Exception 발생!!! 하기 로그 참조"))
            self.logger.exception(e)

        if self.state != -1 and not self.state == 0:
            RunnerLocker.instance().close_locker()

        self.logger.info(self.__format_log_msg("스레드 종료합니다."))

    def processing_loop(self):
        if self.is_back_testing_mode:
            if self.trading_dao.get_latest_trade_price(self.config["stock_code"]) is None:
                self.state = -1
            else :
                self.state = 1

        print(f"{'[백테스트]' if self.is_back_testing_mode else ''} processing_loop 시작 {self.state}")
        while self.run_flag:
            self.refresh_all_data()
            if self.state == -1:
                # 거래 되지 않음
                RunnerLocker.instance().check_locker()
                if not self.run_flag:
                    break
                self.process_state_initial()
            elif self.state == 1:
                self.process_state_one()
            elif self.state == 0:
                self.run_flag = False
                RunnerLocker.instance().close_locker()
                self.logger.info(self.__format_log_msg("Locker Close 하였습니다."))
            time.sleep(0.1)

    def process_state_initial(self):
        print("최초 구매")
        # processing state: -1
        RunnerLocker.instance().open_locker()
        self.logger.info(self.__format_log_msg("B1 매수 타점 도달하였습니다!"))
        self.open_position(self.config["B1"]["qty"])
        self.logger.info(self.__format_log_msg("Locker Open 하였습니다."))
        self.state = 1

    def process_state_one(self):
        # print(f"{"[백테스트]" if self.is_back_testing_mode else ""} 거래 중")
        latest_price = self.trading_dao.get_backtest_latest_trade_price(self.config["stock_code"])
        if latest_price is None:
            self.process_state_initial()
            self.state = 1
            return
        # processing state: 1
        if self.current_price >= latest_price + self.config["S1"]["price"]:
            self.logger.info(self.__format_log_msg("S1 매도 타점 도달하였습니다!"))
            self.close_position(self.config["S1"]["qty"])
        elif self.current_price <= latest_price - self.config["B1"]["price"]:
            self.logger.info(self.__format_log_msg("B2 매수 타점 도달하였습니다!"))
            self.open_position(self.config["B1"]["qty"])

        self.state = 1

    def open_position(self, qty):
        self.trading_dao.open_position(
            self.config["acc_no"], 
            self.config["stock_code"], 
            qty
        )

    def close_position(self, qty):
        try:
            self.trading_dao.close_position(
                self.config["acc_no"], 
                self.config["stock_code"], 
                qty
            )
        except NoSuchStockPositionError:
            self.logger.info(self.__format_log_msg("매도하려고 했으나, 이미 사용자에 의해 전량 매도 되었습니다."))

    def refresh_all_data(self):
        self.current_price = self.trading_dao.get_current_price(self.config["stock_code"])

    def stop_and_save(self):
        self.run_flag = False
        self.config["state"] = self.state
        return self.config

    def __format_log_msg(self, msg):
        return f"{self.config['stock_name']}({self.config['stock_code']}): {msg}"
