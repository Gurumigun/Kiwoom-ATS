import datetime
import json
import logging
import logging.config
import os
import sys

from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from python.src.ats.ConfigParser import ConfigParser
from python.src.ats.RunnerController import Controller
from python.src.ats.dao.KiwoomDAO import KiwoomDAO
from python.src.ats.dao.BacktestDAO import BacktestDAO


def get_market_closeing_time() -> datetime.datetime:
    market_close_time = datetime.datetime.now()
    return market_close_time.replace(hour=15, minute=20, second=0, microsecond=0)


def get_market_start_time() -> datetime.datetime:
    return datetime.datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)


def is_before_market_start_time() -> bool:
    return (get_market_start_time() - datetime.datetime.now()).total_seconds() > 0


def is_after_market_close_time() -> bool:
    return (get_market_closeing_time() - datetime.datetime.now()).total_seconds() < 0


def wait_until_market_start():
    QTest.qWait(
        int((get_market_start_time() - datetime.datetime.now()).total_seconds() * 1000))


def wait_until_market_close():
    QTest.qWait(int((get_market_closeing_time() -
                     datetime.datetime.now()).total_seconds() * 1000))


def get_hms(a, b):
    '''
    a > b
    '''
    time_delta = a - b
    hour = int(time_delta.total_seconds() // 3600)
    minute = int((time_delta.total_seconds() // 60) % 60)
    second = int(time_delta.total_seconds() - hour * 3600 - minute * 60)

    return hour, minute, second


def index():
    with open("./resources/log/logging.json") as f:
        config = json.load(f)
    logging.config.dictConfig(config)

    app = QApplication(sys.argv)

    _is_back_testing_mode = ConfigParser.instance().is_back_testing_mode()
    if _is_back_testing_mode:
        trading_dao = BacktestDAO.instance()
        print("========= 백테스팅 모드입니다. ==========")
        stock_list = ConfigParser.instance().load_back_testing_stock_config()
    else:
        trading_dao = KiwoomDAO.instance()
        print("실제 거래 모드입니다.")
        stock_list = ConfigParser.instance().load_stock_config()

    controller = Controller()

    if stock_list.__len__() == 0:
        print("등록된 종목이 없습니다.")
    else:
        print("===== 주식 목록 =====")
        for stock in stock_list:
            controller.add_runner(stock)
            print(f"{stock['stock_name']}({stock['stock_code']})")
            QTest.qWait(1000)

    if (controller.runner_list.__len__() == 0):
        print("에러: 실행할 종목이 아무것도 없습니다!")
        sys.exit()

    if not _is_back_testing_mode:
        if is_after_market_close_time():
            print("장 종료되었습니다.")
            sys.exit()

        if (is_before_market_start_time()):
            hour, minute, second = get_hms(get_market_start_time(), datetime.datetime.now())
            print(f"\n장 시작 까지 {hour}시간 {minute}분 {second}초 남았습니다.")
            wait_until_market_start()

    print("장 시작하였습니다!\n5초 후 프로그램 가동!!!\a")
    QTest.qWait(5000)
    print("\a")
    controller.run_all()

    if _is_back_testing_mode:
        while True:
            QTest.qWait(1000)
            if all(not runner.run_flag for runner in controller.runner_list):
                break
    else:
        hour, minute, second = get_hms(
            get_market_closeing_time(), datetime.datetime.now())
        print(f"\n장 종료 까지 {hour}시간 {minute}분 {second}초 남았습니다.\n")
        wait_until_market_close()

    print("장 종료")
    controller.stop_and_save_all()
    app.exit()

    print("프로그램 종료")

    if (ConfigParser.instance().load_is_power_off()):
        print("컴퓨터 종료합니다")
        os.system("shutdown /s /t 1")
    else:
        sys.exit()


if __name__ == "__main__":
    index()
