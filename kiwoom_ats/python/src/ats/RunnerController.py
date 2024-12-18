import logging
from typing import List

from PyQt5.QtTest import QTest

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

        print(f"{'[백테스팅]' if ConfigParser.instance().is_back_testing_mode() else ''} 나의 계좌번호 : {config['acc_no']}")
        self.runner_list.append(AtsRunner(config))

    def run_all(self):
        for runner in self.runner_list:
            runner.start()
            print(runner.config["stock_code"])
            QTest.qWait(500)
