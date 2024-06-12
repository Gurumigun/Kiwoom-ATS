import logging
from typing import List

from PyQt5.QtTest import QTest

from python.src.ats.TradingDAO import TradingDAO
from python.src.ats.AtsRunner import AtsRunner
from python.src.ats.ConfigParser import ConfigParser


class Controller():
    _log = logging.getLogger(__name__)
    runner_list: List[AtsRunner]

    def __init__(self):
        self.runner_list = list()

    def add_runner(self, config):
        '''예수금 '''
        config["acc_no"] = ConfigParser.instance().get_account_number()

        print(f"{"[백테스팅]" if ConfigParser.instance().is_back_testing_mode() else ""} 나의 계좌번호 : {config["acc_no"]}")
        self.runner_list.append(AtsRunner(config))

    def run_all(self):
        for runner in self.runner_list:
            runner.start()
            print(runner.config["stock_code"])
            QTest.qWait(500)

    def stop_and_save_all(self):
        data_list = list()
        # for runner in self.runner_list:
        #     data = runner.stop_and_save()
        #
        #     if not (runner.state == -1):
        #         if runner.state == 0:
        #             self._log.info(f"{data['stock_name']}({data['stock_code']}) DB에서 삭제합니다.")
        #             TradingDAO.instance().remove_trading_data(data["stock_code"])
        #         else:
        #             self._log.info(f"{data['stock_name']}({data['stock_code']}) 거래내역 저장합니다.")
        #             data_list.append(data)
        #             TradingDAO.instance().save_unfinished_trading_data(data)
        #             try:
        #                 ConfigParser.instance().remove_stock_config(data["stock_code"])
        #             except(KeyError):
        #                 pass
        #
        # ConfigParser.instance().add_unfinished_stock(data_list)