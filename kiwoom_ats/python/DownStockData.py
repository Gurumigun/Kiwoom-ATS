import sqlite3
import time

import pandas as pd
# from PyQt5 import uic
# from PyQt5.QtWidgets import QMainWindow
# from pykiwoom.kiwoom import Kiwoom

# form_class = uic.loadUiType("main_ui.ui")[0]


# class tradesystem(QMainWindow, form_class):
#     def __init__(self):
#         super().__init__()
#         self.setupUi(self)  ## GUI 켜기
#         self.setWindowTitle("주식 프로그램")  ## 프로그램 화면 이름 설정
#         """키움증권 Open API 객체 생성"""
#         # self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")  ## OpenAPI 시작
#         # """로그인 요청 함수"""
#         # self.kiwoom.dynamicCall("CommConnect()")  ## 로그인 요청
#         kiwoom = Kiwoom()
#         # self.kiwoom.OnReceiveTrData.connect(self.handle_OnReceiveTrData)
#         kiwoom.CommConnect(block=True)

def login():
    kiwoom = Kiwoom()
    kiwoom.CommConnect()
    return kiwoom

def collect_stock_data(kiwoom, code, start_date):
    data = kiwoom.block_request("opt10080",
                                 종목코드=code,
                                 기준일자=start_date,
                                 수정주가구분=1,
                                 output="주식일봉차트조회",
                                 데이터개수=1000000,
                                 next=0)
    return data
def save_to_database(code, data):
    connection = sqlite3.connect('src/resources/backtest/stock_data.db')
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS back_testing_stock_data
        ( 
        stock_code TEXT,
        current_price INTEGER, 
        volume INTEGER, 
        transaction_time TEXT, 
        open_price INTEGER, 
        high_price INTEGER, 
        low_price INTEGER, 
        price_correction_division INTEGER, 
        correction_ratio REAL, 
        major_industry_division TEXT, 
        minor_industry_division TEXT, 
        stock_info TEXT, 
        price_correction_event TEXT, 
        previous_day_closing_price INTEGER)
    ''')


    cursor.execute('''
        SELECT * FROM back_testing_stock_data WHERE stock_code = ? AND transaction_time = ?
    ''', (code, data['체결시간']))
    rows = cursor.fetchall()

    if len(rows) == 0:
        cursor.execute('''
            INSERT INTO back_testing_stock_data 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (str(code),
              data['현재가'],
              data['거래량'],
              int(data['체결시간']),
              int(data['시가']),
              int(data['고가']),
              int(data['저가']),
              data['수정주가구분'],
              data['수정비율'],
              data['대업종구분'],
              data['소업종구분'],
              data['종목정보'],
              data['수정주가이벤트'],
              data['전일종가']))
        connection.commit()
    connection.close()

def main():
    kiwoom = login()
    # ETF 종목 코드를 입력하세요 (예: KODEX 200)
    etf_code = "233740"

    # 10년 전 날짜를 계산합니다.
    end_date = "20230611"
    start_date = "20100531"

    # TR 요청 (연속조회)
    dfs = []
    df = kiwoom.block_request("opt10080",
                              종목코드=etf_code,
                              기준일자=end_date,
                              수정주가구분=1,
                              output="주식분봉차트조회",
                              next=0)
    print(df.head())
    dfs.append(df)

    while kiwoom.tr_remained:
        df = kiwoom.block_request("opt10080",
                                  종목코드=etf_code,
                                  기준일자=end_date,
                                  수정주가구분=1,
                                  output="주식분봉차트조회",
                                  next=2)
        dfs.append(df)
        time.sleep(0.5)

    df = pd.concat(dfs)
    df.to_excel(f"기준일자={end_date}_{etf_code}.xlsx")

if __name__ == "__main__":
    # main()
    stock_code = "233740"
    data = pd.read_excel('src/resources/backtest/test_233740.XLSX')

    for index, row in data.iterrows():
        save_to_database(stock_code, row.to_dict())

    # app = QApplication(sys.argv)
    # myWindow = tradesystem()
    # myWindow.show()
    # app.exec()