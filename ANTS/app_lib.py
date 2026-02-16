import pandas as pd
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from ANTS.data import ticker_data_download
import mojito
from dotenv import load_dotenv
import os
import dash_bootstrap_components as dbc
from dash_tvlwc.types import ColorType, SeriesType
import FinanceDataReader as fdr
import pandas_ta as ta
import warnings

warnings.filterwarnings("ignore")
load_dotenv()

def get_list(catagory:str) :
    with create_engine(os.getenv('DB_URL')).connect() as conn:
        data = pd.read_sql(f'SELECT TICKER, NAME, INDUSTRY, MARKETCAP, PER, PBR, PSR, EV_EBITDA, PERZ, PBRZ, PSRZ, EV_EBITDAZ, PRICEZ, SALES_GROWTH, OP_GROWTH, NP_GROWTH FROM data', conn)
    
    data['id'] = data['ticker']
    data['ticker'] = "[" + data['ticker'] + "](https://finance.naver.com/item/main.nhn?code=" + data['ticker'] + ")" 
    
    return data

def check_etf(ticker) :
    etfs = fdr.StockListing('ETF/KR')

    is_etf = ticker in etfs['Symbol'].values
    return is_etf
    

def get_data(ticker, column_id) :
    
    if ticker == '' : return []
    else : 
        if column_id == 'ETF' :
            data = fdr.DataReader(ticker)
            if len(data) != 0 :
                data = data[(data['Close'] != 0) & (data['Volume'] != 0)]
            data = data.reset_index() 
            data.columns = data.columns.str.upper()
            column_id = 'pricez' 
        else :
            broker = mojito.KoreaInvestment(
                        api_key=os.getenv('KIS_APP_KEY'),
                        api_secret=os.getenv('KIS_APP_SECRET'),
                        acc_no=os.getenv('KIS_ACCOUNT'),
                        mock=False
                    )

            data = ticker_data_download(ticker=ticker, current_year_length=250, broker=broker, total='X')
            data = data.reset_index() 

        if column_id == 'pbrz' or column_id == 'pbr' : 
            per_share = 'ADJ_BPS'
            indicator = 'PBR'
        elif column_id == 'psrz' or column_id == 'psr' : 
            per_share = 'ADJ_SPS'
            indicator = 'PSR'
        elif column_id == 'ev_ebitdaz' or column_id == 'ev_ebitda' : 
            per_share = 'ADJ_EBITDA'
            indicator = 'EV_EBITDA'
        elif column_id == 'pricez' : 
            indicator = 'PRICE'
        else : 
            per_share = 'ADJ_EPS'
            indicator = 'PER'

        if column_id != 'pricez' :
            mean = data[data[indicator] != 0][indicator].mean()
            std = data[data[indicator] != 0][indicator].std(ddof=0)

        if indicator == 'EV_EBITDA':
            for z in [-2.0, -1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5, 2.0]:
                ratio = mean + z * std
                data[f'{z:+.1f} {indicator}Z'] = (ratio * data['ADJ_EBITDA'] + data['ADJ_DEBT_CASH']) / data['SHARE']
        elif indicator == 'PRICE' :
            model = LinearRegression()
            model.fit(data.index.values.reshape(-1, 1), data['CLOSE'])
            
            data['BASE'] = model.predict(data.index.values.reshape(-1, 1))
            data['Residuals'] = data['CLOSE'] - data['BASE']
            std_dev = data['Residuals'].std()
            data['PRICEZ'] = data['Residuals'] / std_dev
            
            for z in [-2.0, -1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5, 2.0]:
                data[f'{z:+.1f} {indicator}Z'] = data['BASE'] + z * std_dev

        else:
            for z in [-2.0, -1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5, 2.0]:
                data[f'{z:+.1f} {indicator}Z'] = (mean + z * std) * data[per_share]

        ohlc_data, zscore_0_data, zscore_p1_data, zscore_p2_data, zscore_p3_data, zscore_p4_data, zscore_m1_data, zscore_m2_data, zscore_m3_data, zscore_m4_data, ma60_data, ma120_data, ma240_data = [], [], [], [], [], [], [], [], [], [], [], [], []
        
        for index, row in data.iterrows():
            if row[f'-2.0 {indicator}Z'] < 0 :
                row[f'-2.0 {indicator}Z'] = 0
            if row[f'-1.5 {indicator}Z'] < 0 :
                row[f'-1.5 {indicator}Z'] = 0
            if row[f'-1.0 {indicator}Z'] < 0 :
                row[f'-1.0 {indicator}Z'] = 0
            if row[f'-0.5 {indicator}Z'] < 0 :
                row[f'-0.5 {indicator}Z'] = 0
            if row[f'+0.0 {indicator}Z'] < 0 :
                row[f'+0.0 {indicator}Z'] = 0
            if row[f'+2.0 {indicator}Z'] < 0 :
                row[f'+2.0 {indicator}Z'] = 0
            if row[f'+1.5 {indicator}Z'] < 0 :
                row[f'+1.5 {indicator}Z'] = 0
            if row[f'+1.0 {indicator}Z'] < 0 :
                row[f'+1.0 {indicator}Z'] = 0
            if row[f'+0.5 {indicator}Z'] < 0 :
                row[f'+0.5 {indicator}Z'] = 0
            
            ohlc = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'open': row['OPEN'],
                'high': row['HIGH'],
                'low': row['LOW'],
                'close': row['CLOSE']
            }
            zscore_m1 = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'value': row[f'-0.5 {indicator}Z']
            }
            zscore_m2 = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'value': row[f'-1.0 {indicator}Z']
            }
            zscore_m3 = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'value': row[f'-1.5 {indicator}Z']
            }
            zscore_m4 = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'value': row[f'-2.0 {indicator}Z']
            }
            zscore_0 = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'value': row[f'+0.0 {indicator}Z']
            }
            zscore_p1 = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'value': row[f'+0.5 {indicator}Z']
            }
            zscore_p2 = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'value': row[f'+1.0 {indicator}Z']
            }
            zscore_p3 = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'value': row[f'+1.5 {indicator}Z']
            }
            zscore_p4 = {
                'time': row['DATE'].strftime('%Y-%m-%d'),
                'value': row[f'+2.0 {indicator}Z']
            }

            ohlc_data.append(ohlc)
            #volume_data.append(volume)
            zscore_0_data.append(zscore_0)
            zscore_m1_data.append(zscore_m1)
            zscore_m2_data.append(zscore_m2)
            zscore_m3_data.append(zscore_m3)
            zscore_m4_data.append(zscore_m4)
            zscore_p1_data.append(zscore_p1)
            zscore_p2_data.append(zscore_p2)
            zscore_p3_data.append(zscore_p3)
            zscore_p4_data.append(zscore_p4)
            #ma60_data.append(ma60)
            #ma120_data.append(ma120)
            #ma240_data.append(ma240)
        return [ohlc_data, zscore_p4_data, zscore_p3_data, zscore_p2_data, zscore_p1_data, zscore_0_data, zscore_m1_data, zscore_m2_data, zscore_m3_data, zscore_m4_data]

def get_title(ticker, column_id) :
    with create_engine(os.getenv('DB_URL')).connect() as conn:
        data = pd.read_sql(f"SELECT NAME FROM data WHERE TICKER = '{ticker}'", conn)

    if column_id == 'pbrz' : indicator = 'PBR'
    elif column_id == 'pbr' : indicator = 'PBR'
    elif column_id == 'psrz' : indicator = 'PSR'
    elif column_id == 'psr' : indicator = 'PSR'
    elif column_id == 'ev_ebitda' : indicator = 'EV/EBITDA'
    elif column_id == 'ev_ebitdaz' : indicator = 'EV/EBITDA'
    elif column_id == 'pricez' : indicator = 'PRICE'
    else : indicator = 'PER'
    
    return [data.iloc[0, 0], dbc.Badge(indicator, color="dark", className="ms-1")]


series_types = [SeriesType.Candlestick, SeriesType.Line, SeriesType.Line, SeriesType.Line, SeriesType.Line, SeriesType.Line, SeriesType.Line, SeriesType.Line, SeriesType.Line, SeriesType.Line, SeriesType.Line, SeriesType.Line, SeriesType.Line]

chart_options={
                'layout': {
                    'background': {'type': ColorType.Solid, 'color': 'white'},
                    'textColor': 'black',
                    'fontFamily': 'Nanum Myeongjo, serif',
                },
                'grid': {
                    'vertLines': {'visible': True, 'color': 'rgba(255,255,255,0.1)'},
                    'horzLines': {'visible': True, 'color': 'rgba(255,255,255,0.1)'},
                },
                'localization': {
                    'locale': 'ko-KR',
                    'priceFormatter': "(function(price) {return price.toFixed(0) + '$';})",
                },
                'watermark': {
                    'color': 'darkgray',
                    'visible': 'true',
                    'text': 'ANTS Investment',
                    'fontFamily': 'Nanum Myeongjo, serif',
                },
            }

series_options=[{#'borderColor': 'black'
                },{
                    'lineWidth': 1,
                    'lineStyle' : 3,
                    'color' : 'darkred',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 0.5,
                    'lineStyle' : 2,
                    'color' : 'darkred',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 1,
                    'lineStyle' : 3,
                    'color' : 'red',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 0.5,
                    'lineStyle' : 2,
                    'color' : 'red',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 1,
                    'lineStyle' : 3,
                    'color' : 'dimgray',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 0.5,
                    'lineStyle' : 2,
                    'color' : 'blue',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 1,
                    'lineStyle' : 3,
                    'color' : 'blue',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 0.5,
                    'lineStyle' : 2,
                    'color' : 'darkblue',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 1,
                    'lineStyle' : 3,
                    'color' : 'darkblue',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                }]
"""
                ,{
                    'lineWidth': 1,
                    'lineStyle' : 0,
                    'color' : 'yellow',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 1,
                    'lineStyle' : 0,
                    'color' : 'gold',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                },{
                    'lineWidth': 1,
                    'lineStyle' : 0,
                    'color' : 'orange',
                    'lastValueVisible': False,
                    'priceLineVisible': False
                }]

            ,{
                'color': '#26a69a',
                'priceFormat': {'type': 'volume'},
                'priceScaleId': '',
                'scaleMargins': {'top': 0.9, 'bottom': 0},
                'priceLineVisible': False
            }
"""