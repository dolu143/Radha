from SmartApi import SmartConnect
import credentials
from credentials import API_KEY
from credentials import CLIENT_ID
from credentials import PIN
from credentials import TOKEN
from credentials import FEED_TOKEN
from credentials import TOKEN_MAP
import pyotp
import logzero
import requests
import pandas as pd
import xlsxwriter as xw
import datetime


def intializeSymbolTokenMap():
    url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
    d = requests.get(url).json()
    global token_df
    token_df = pd.DataFrame.from_dict(d)
    token_df['expiry'] = pd.to_datetime(token_df['expiry'])
    token_df = token_df.astype({'strike': float})
    credentials.TOKEN_MAP = token_df


def getTokenInfo(exch_seg, instrumenttype, symbol, strike_price, pe_ce):
    df = credentials.TOKEN_MAP
    strike_price = strike_price * 100
    if exch_seg == 'NSE' and instrumenttype == '':
        eq_df = df[(df['exch_seg'] == 'NSE')
                   & (df['symbol'].str.contains('EQ'))]
        return eq_df[eq_df['name'] == symbol]
    elif exch_seg == 'NSE' and instrumenttype == 'AMXIDX':
        return df[(df['exch_seg'] == 'NSE')
                  & (df['instrumenttype'] == instrumenttype) &
                  (df['name'] == symbol)]
    elif exch_seg == 'BSE' and instrumenttype == 'AMXIDX':
        return df[(df['exch_seg'] == 'BSE')
                  & (df['instrumenttype'] == instrumenttype) &
                  (df['name'] == symbol)]
    elif exch_seg == 'NFO' and ((instrumenttype == 'FUTSTK') or
                                (instrumenttype == 'FUTIDX')):
        return df[(df['exch_seg'] == 'NFO')
                  & (df['instrumenttype'] == instrumenttype) &
                  (df['name'] == symbol)].sort_values(by=['expiry'])
    elif exch_seg == 'NFO' and (instrumenttype == 'OPTSTK'
                                or instrumenttype == 'OPTIDX'):
        return df[(df['exch_seg'] == 'NFO')
                  & (df['instrumenttype'] == instrumenttype) &
                  (df['name'] == symbol) & (df['strike'] == strike_price) &
                  (df['symbol'].str.endswith(pe_ce))].sort_values(
                      by=['expiry'])

def getstrike(ltp, off, ce_pe):
    r = round(ltp, -2)
    print(r)
    d = r - ltp
    if ce_pe == 'PE':
        off = -1*off

    if off == 0:
        strike = round(ltp, -2)
        print("ATM Strike:", strike)
        return strike

    elif off < 0:
        if d < 51 and d > 0:
            strike = round(ltp, -2) + off * 100
            print("Strike:", strike)
            return strike
        elif d == 0:
            strike = ltp + off * 100
            print("Strike:", strike)
            return strike
        elif d < 0 and d > -51:
            strike = round(ltp, -2) + off * 100
            print("Strike:", strike)
            return strike

    elif off > 0:
        if d < 51 and d > 0:
            strike = round(ltp, -2) + off * 100
            print("Strike:", strike)
            return strike
        elif d == 0:
            strike = ltp + off * 100
            print("Strike:", strike)
            return strike
        elif d < 0 and d > -51:
            strike = round(ltp, -2) + off * 100
            print("Strike:", strike)
            return strike
            

def login():
    global smartApi
    try:
        totp = pyotp.TOTP(TOKEN).now()
    except Exception as e:
        logger.error("Invalid Token: The provided token is not valid.")
        raise e
    smartApi = SmartConnect(API_KEY)
    data = smartApi.generateSession(CLIENT_ID, PIN, totp)
    refreshToken = data['data']['refreshToken']
    feedToken = smartApi.getfeedToken()
    credentials.FEED_TOKEN = feedToken
    print(feedToken)
    if data['status'] == False:
        logger.error(data)
        print("Log In Error Occured")
    return smartApi


def logout():
    try:
        logout = smartApi.terminateSession(credentials.CLIENT_ID)
        print("Your Session was {}".format(logout['data']))
    except Exception as e:
        print("Logout failed: {}".format(e.message))


def ltp(exch_seg, symbol, token):
    try:
        df = smartApi.ltpData(exch_seg, symbol, token)
        return (df)
    except Exception as e:
        print("Get LTP failed: {}".format(e.message))


def place_order(token, symbol, qty, exch_seg, buy_sell, ordertype, price):
    try:
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": buy_sell,
            "exchange": exch_seg,
            "ordertype": ordertype,
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": price,
            "squareoff": "0",
            "stoploss": "0",
            "quantity": qty
        }
        orderId = smartApi.placeOrder(orderparams)
        print("The order id is: {}".format(orderId))
    except Exception as e:
        print("Order placement failed: {}".format(e.message))


#Historic api
def histcandle(exch_seg, token, timeframe, fromdate, todate):
    try:
        historicParam = {
            "exchange": exch_seg,
            "symboltoken": token,
            "interval": timeframe,
            "fromdate": fromdate,
            "todate": todate
        }
        data = smartApi.getCandleData(historicParam)
        return data
    except Exception as e:
        print("Historic Api failed: {}".format(e.message))


def fetch_onemin_oneday(exch_seg, token, date):
    timeframe = 'ONE_MINUTE'
    fromdate = date
    day = fromdate[8:10]
    month = fromdate[5:7]
    year = fromdate[0:4]
    todate = datetime.datetime(int(year), int(month), int(day), 15, 29)
    todate = todate.strftime('%Y-%m-%d %H:%M')
    #todate = year+'-'+month+'-'+day+' '+'15:29'
    histdata = histcandle(exch_seg, token, timeframe, fromdate, todate)
    return histdata


def write_toxl(exch_seg, token, timeframe, fromdate, todate):
    columns = ["time", "o", "h", "l", "c", "v"]
    date = fromdate
    histdata = fetch_onemin_oneday(exch_seg, token, date)
    histdata = pd.DataFrame(histdata["data"], columns=columns)
    histdata["time"] = pd.to_datetime(histdata["time"],
                                      format="%Y-%m-%dT%H:%M:%S")
    print(histdata)
    wb = xw.Workbook("//content//Krishna//Nifty.xlsx",
                     {'remove_timezone': True})
    wb1 = wb.add_worksheet("NIFTY")
    wb1.write_row(0, 0, columns)
    format1 = wb.add_format({'num_format': 'dd/mm/yy hh:mm'})
    wb1.write_column(1, 0, histdata['time'], format1)
    wb1.write_column(1, 1, histdata['o'])
    wb1.write_column(1, 2, histdata['h'])
    wb1.write_column(1, 3, histdata['l'])
    wb1.write_column(1, 4, histdata['c'])
    wb1.write_column(1, 5, histdata['v'])
    wb.close()
