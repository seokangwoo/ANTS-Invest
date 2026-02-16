from pykrx import stock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, types
from dotenv import load_dotenv
import os

dtype = {
    'DATEDATA': types.DATE(),
    'CLOSE': types.FLOAT(),
    'OPEN': types.FLOAT(),
    'HIGH': types.FLOAT(),
    'LOW': types.FLOAT(),
    'MARKETCAP': types.FLOAT(),
    'VOLUME': types.FLOAT(),
    'VALUE': types.FLOAT(),
    'DIV': types.FLOAT(),
    'EPS': types.FLOAT(),
    'FWD_EPS': types.FLOAT(),
    'BPS': types.FLOAT(),
    'DPS': types.FLOAT(),
    'NEXTEPS': types.FLOAT(),
    'NEXTBPS': types.FLOAT(),
    'NEXTDPS': types.FLOAT(),
    'ADJEPS': types.FLOAT(),
    'ADJBPS': types.FLOAT(),
    'ADJDPS': types.FLOAT(),
    'PER': types.FLOAT(),
    'PBR': types.FLOAT(),
    'DBR': types.FLOAT(),
    'PERZ': types.FLOAT(),
    'PBRZ': types.FLOAT(),
    'DBRZ': types.FLOAT(),
}

def indicator_daily_adjustment(current_year_value, next_year_value, year_length) :
    if (current_year_value == 0) or (np.isnan(current_year_value)) or (next_year_value == 0) or (np.isnan(next_year_value)) :
        daily_adjustment = 0
    else :
        daily_adjustment = (current_year_value - next_year_value) / year_length
    return daily_adjustment

def find_last_value(list_adjvalue:list, current_year_data) :
    if len(list_adjvalue) > 0 :
        if list_adjvalue[-1] == 0 :
            if current_year_data == 0 : last_value = 0
            else : last_value = current_year_data
        else : last_value = list_adjvalue[-1]
    else :
        if current_year_data == 0 : last_value = 0
        else : last_value = current_year_data
    return last_value
    
def ticker_data_download(ticker: str, start_date: str, end_date: str, current_year_length: int) :
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    
    with create_engine(os.getenv('DB_URL')).connect() as conn:
        yearly_data = pd.read_sql(f"SELECT * FROM tickeryeardata WHERE TICKER='{ticker}' ORDER BY YEAR", conn)
        
    if len(yearly_data) <= 3 :
        start_date = datetime.strptime('1990-01-01', '%Y-%m-%d')
    try :
        fundamental_year = stock.get_market_fundamental(start_date, end_date, ticker, freq='y')
        market_year = stock.get_market_cap(start_date, end_date, ticker, freq='y') 
    except :
        return

    yearly_data = pd.concat([fundamental_year, market_year], axis=1, join='outer')
    yearly_data = yearly_data[['Shares', 'DIV', 'EPS', 'FWD_EPS', 'BPS', 'DPS']]
    yearly_data['Ticker'] = ticker
    yearly_data.index = yearly_data.index.year
    if not(np.isnan(yearly_data[yearly_data['EPS'].isnull()].index.max())) :
        yearly_data.drop(yearly_data.loc[:yearly_data[yearly_data['EPS'].isnull()].index.max()].index, inplace=True)
    yearly_data.index.name = 'YEAR'
    
    yearly_data.reset_index(inplace=True)
    yearly_data.columns = yearly_data.columns.str.upper()
    yearly_data.set_index(['YEAR','TICKER'], drop=True, inplace=True)
    
    with create_engine(os.getenv('DB_URL'), use_ansi=True).connect() as conn:
        conn.execute(f"DELETE FROM tickeryeardata WHERE YEAR >= '{start_date.year}' AND YEAR <= '{end_date.year}' AND TICKER = '{ticker}'")
        yearly_data.to_sql('tickeryeardata', conn, if_exists='append', index=True, index_label=['YEAR', 'TICKER'])
        yearly_data = pd.read_sql(f"SELECT * FROM tickeryeardata WHERE TICKER='{ticker}' ORDER BY YEAR", conn)
    
    if len(yearly_data) <= 2 :
        return
    
    yearly_data.columns = yearly_data.columns.str.upper()
    yearly_data.reset_index(inplace=True)
    yearly_data.set_index(['YEAR'], drop=True, inplace=True)
    lastShare = yearly_data.iloc[-1]['SHARES']

    yearly_data['EPS'] = yearly_data['EPS'] * yearly_data['SHARES'] / lastShare 
    yearly_data['BPS'] = yearly_data['BPS'] * yearly_data['SHARES'] / lastShare 
    yearly_data['DPS'] = yearly_data['DPS'] * yearly_data['SHARES'] / lastShare 

    yearly_data['EPS'] = yearly_data['EPS'].shift(-1)
    yearly_data['BPS'] = yearly_data['BPS'].shift(-1)
    yearly_data['DPS'] = yearly_data['DPS'].shift(-1)
    
    if datetime.today().month < 4 :
        yearly_data.loc[datetime.today().year-1, 'EPS'] = yearly_data.loc[datetime.today().year-2, 'FWD_EPS']
        yearly_data.loc[datetime.today().year-1, 'BPS'] = yearly_data.loc[datetime.today().year-2, 'BPS'] + yearly_data.loc[datetime.today().year-2, 'EPS']
        yearly_data.loc[datetime.today().year-1, 'DPS'] = yearly_data.loc[datetime.today().year-2, 'DPS']

    yearly_data['NEXTEPS'] = yearly_data['EPS'].shift(-1)
    yearly_data['NEXTBPS'] = yearly_data['BPS'].shift(-1)
    yearly_data['NEXTDPS'] = yearly_data['DPS'].shift(-1)

    yearly_data = yearly_data[(yearly_data['EPS'] != 0) | (yearly_data['BPS'] != 0)]
    
    yearly_data.index.name = 'YEAR'
    yearly_data.reset_index(inplace=True)
    yearly_data.set_index(['YEAR'], drop=True, inplace=True)
    
    daily_data = stock.get_market_cap(start_date, end_date, ticker)
    daily_data = daily_data[daily_data['Volume'] != 0]
        
    daily_data.index.name = 'DATEDATA'
    daily_data.reset_index(inplace=True)
    daily_data.columns = daily_data.columns.str.upper()
    daily_data.set_index(['DATEDATA'], drop=True, inplace=True)
    
    start_date = start_date.strftime('%Y-%m-%d')
    end_date = end_date.strftime('%Y-%m-%d')

    with create_engine(os.getenv('DB_URL')).connect() as conn:
        try :
            conn.execute(f'DELETE FROM "{ticker}" WHERE DATEDATA >= TO_DATE(\'{start_date}\', \'YYYY-MM-DD\') AND DATEDATA <= TO_DATE(\'{end_date}\', \'YYYY-MM-DD\')')
            #daily_data.to_sql(ticker, conn, if_exists='replace', index=True, index_label=['DATEDATA'], dtype=dtype)
            daily_data.to_sql(ticker, conn, if_exists='append', index=True, index_label=['DATEDATA'], dtype=dtype)
            daily_data = pd.read_sql(f'SELECT DATEDATA, OPEN, HIGH, LOW, CLOSE, MARKETCAP, VOLUME, VALUE FROM "{ticker}" ORDER BY DATEDATA', conn)
        except :
            daily_data.to_sql(ticker, conn, if_exists='replace', index=True, index_label=['DATEDATA'], dtype=dtype)
            daily_data = pd.read_sql(f'SELECT DATEDATA, OPEN, HIGH, LOW, CLOSE, MARKETCAP, VOLUME, VALUE FROM "{ticker}" ORDER BY DATEDATA', conn)
        
    daily_data.columns = daily_data.columns.str.upper()
    daily_data.set_index(['DATEDATA'], drop=True, inplace=True)
    daily_data.index = pd.to_datetime(daily_data.index)

    data = pd.merge(daily_data, yearly_data, how='left', left_on=daily_data.index.year, right_on=yearly_data.index)
    data['DATEDATA'] = daily_data.index
    data.set_index('DATEDATA', drop=True, inplace=True)
    data.rename(columns = {'key_0':'YEAR'},inplace=True)
    
    daily_adjustment=pd.DataFrame({'DATEDATA': [], 'ADJEPS': [], 'ADJBPS': [], 'ADJDPS': [], 'ADJCPS': [], 'ADJSPS': [], 'ADJBCPS': []})
    list_index, list_adjeps, list_adjbps, list_adjcps, list_adjdps, list_adjsps, list_adjbcps = [], [], [], [], [], [], []
    
    for year_index, current_year_data in yearly_data.iterrows() :

        if year_index == datetime.today().year :
            year_length = current_year_length
        else :
            year_length = len(data[data['YEAR']==year_index])

        if (current_year_data.NEXTEPS == 0) or (np.isnan(current_year_data.NEXTEPS)) :
            if (current_year_data.FWD_EPS == 0) or (np.isnan(current_year_data.FWD_EPS)) :
                EPS_daily_adjustment = 0    
            else :
                if (current_year_data.EPS == 0) or (np.isnan(current_year_data.EPS)) :
                    EPS_daily_adjustment = (current_year_data.FWD_EPS - last_EPS) / year_length
                else :
                    EPS_daily_adjustment = (current_year_data.FWD_EPS - current_year_data.EPS) / year_length
        else :
            EPS_daily_adjustment = (current_year_data.NEXTEPS - current_year_data.EPS) / year_length

        if (current_year_data.BPS == 0) or (np.isnan(current_year_data.BPS)) :
            BPS_daily_adjustment = 0
        else :
            if (current_year_data.NEXTBPS == 0) or (np.isnan(current_year_data.NEXTBPS)) :
                if (current_year_data.FWD_EPS == 0) or (np.isnan(current_year_data.FWD_EPS)) :
                    BPS_daily_adjustment = 0
                else :
                    BPS_daily_adjustment = current_year_data.FWD_EPS / year_length
            else :         
                BPS_daily_adjustment = (current_year_data.NEXTBPS - current_year_data.BPS) / year_length
        
        DPS_daily_adjustment = indicator_daily_adjustment(current_year_data.DPS, current_year_data.NEXTDPS, year_length)
        
        last_EPS = find_last_value(list_adjeps, current_year_data.EPS)
        last_BPS = find_last_value(list_adjbps, current_year_data.BPS)
        last_DPS = find_last_value(list_adjdps, current_year_data.DPS)

        for data_index, current_data in data[data['YEAR'] == year_index].iterrows() :
            list_index.append(data_index)
            last_EPS = last_EPS + EPS_daily_adjustment
            last_BPS = last_BPS + BPS_daily_adjustment
            last_DPS = last_DPS + DPS_daily_adjustment
            list_adjeps.append(last_EPS)
            list_adjbps.append(last_BPS)
            list_adjdps.append(last_DPS)

    daily_adjustment = pd.DataFrame({'DATEDATA': list_index,
                                    'ADJEPS': list_adjeps, 
                                    'ADJBPS': list_adjbps,
                                    'ADJDPS': list_adjdps}) 

    daily_adjustment.set_index('DATEDATA', inplace=True)

    data = pd.concat([data, daily_adjustment], axis=1)
    data.drop(columns=['YEAR', 'TICKER', 'index'], inplace=True)
    
    data['PER'] = data['CLOSE'] / data['ADJEPS']
    data['PBR'] = data['CLOSE'] / data['ADJBPS']
    data['DBR'] = data['ADJDPS'] / data['CLOSE']

    data.replace([np.inf, -np.inf, np.nan], 0, inplace=True)

    data['PERZ'] = (data['PER'] - data[data['PER'] != 0]['PER'].mean()) / data[data['PER'] != 0]['PER'].std(ddof=0)
    data['PBRZ'] = (data['PBR'] - data[data['PBR'] != 0]['PBR'].mean()) / data[data['PBR'] != 0]['PBR'].std(ddof=0)
    data['DBRZ'] = (data['DBR'] - data[data['DBR'] != 0]['DBR'].mean()) / data[data['DBR'] != 0]['DBR'].std(ddof=0)
  
    data.index.name = 'DATEDATA'
    data.index = pd.to_datetime(data.index, format='%Y-%m-%d')

    with create_engine(os.getenv('DB_URL')).connect() as conn:
        data.to_sql(ticker, conn, if_exists='replace', index=True, index_label=['DATEDATA'], dtype=dtype)

    data['TICKER'] = ticker
    data.reset_index(inplace=True)
    data.set_index(['DATEDATA','TICKER'], drop=True, inplace=True)

    data['NAME'] = stock.get_market_ticker_name(ticker)

    with create_engine(os.getenv('DB_URL')).connect() as conn:
        conn.execute(f"DELETE FROM data WHERE TICKER = '{ticker}'")
        data.iloc[-1:].to_sql('data', conn, if_exists='append', index=True, index_label=['DATEDATA', 'TICKER'])

def index_data_download(ticker: str, start_date: str, end_date: str, current_year_length: int) :
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    
    with create_engine(os.getenv('DB_URL')).connect() as conn:
        yearly_data = pd.read_sql(f"SELECT * FROM indexyeardata WHERE TICKER='{ticker}' ORDER BY YEAR", conn)

    if len(yearly_data) <= 3 :
        start_date = datetime.strptime('1990-01-01', '%Y-%m-%d')
    

    yearly_data = stock.get_index_fundamental(start_date, (end_date-timedelta(days=1)), ticker)

    yearly_data.index.name = 'DATEDATA'
    yearly_data['YEAR'] = yearly_data.index.year
    yearly_data = yearly_data.reset_index()
    yearly_data.columns = yearly_data.columns.str.upper()
    yearly_data = yearly_data[yearly_data.groupby('YEAR')['DATEDATA'].transform('max') == yearly_data['DATEDATA']]
    yearly_data.pop('DATEDATA')

    yearly_data['TICKER'] = ticker
    
    if not(np.isnan(yearly_data[yearly_data['PER'].isnull()].index.max())) :
        yearly_data.drop(yearly_data.loc[:yearly_data[yearly_data['PER'].isnull()].index.max()].index, inplace=True)
 
    yearly_data.reset_index(inplace=True)
    yearly_data.set_index(['YEAR','TICKER'], drop=True, inplace=True)
    yearly_data.pop('index')
    yearly_data.pop('CHANGE')
    
    with create_engine(os.getenv('DB_URL')).connect() as conn:
        conn.execute(f"DELETE FROM indexyeardata WHERE YEAR >= '{start_date.year}' AND YEAR <= '{end_date.year}' AND TICKER = '{ticker}'")
        yearly_data.to_sql('indexyeardata', conn, if_exists='append', index=True, index_label=['YEAR', 'TICKER'])
        yearly_data = pd.read_sql(f"SELECT * FROM indexyeardata WHERE TICKER='{ticker}' ORDER BY YEAR", conn)

    if len(yearly_data) <= 2 :        
        return
    
    yearly_data.columns = yearly_data.columns.str.upper()
    yearly_data.set_index(['YEAR'], drop=True, inplace=True)
    yearly_data.pop('TICKER')
    
    yearly_data['EPS'] = yearly_data['CLOSE'] / yearly_data['PER']
    yearly_data['FWD_EPS'] = yearly_data['CLOSE'] / yearly_data['FWD_PER']    
    yearly_data['BPS'] = yearly_data['CLOSE'] / yearly_data['PBR']
    yearly_data['DPS'] = yearly_data['DBR'] / yearly_data['CLOSE']

    yearly_data['EPS'] = yearly_data['EPS'].shift(-1)
    yearly_data['BPS'] = yearly_data['BPS'].shift(-1)
    yearly_data['DPS'] = yearly_data['DPS'].shift(-1)

    yearly_data['NEXTEPS'] = yearly_data['EPS'].shift(-1)
    yearly_data['NEXTBPS'] = yearly_data['BPS'].shift(-1)
    yearly_data['NEXTDPS'] = yearly_data['DPS'].shift(-1)
    
    yearly_data.replace([np.inf, -np.inf, np.nan], 0, inplace=True)
    yearly_data.fillna(0, inplace=True)
    
    daily_data = stock.get_index_ohlcv(start_date, end_date, ticker)
    daily_data = daily_data[daily_data['Volume'] != 0]
    daily_data.index.name = 'DATEDATA'

    daily_data.reset_index(inplace=True)
    daily_data.columns = daily_data.columns.str.upper()
    daily_data.set_index(['DATEDATA'], drop=True, inplace=True)

    start_date = start_date.strftime('%Y-%m-%d')
    end_date = end_date.strftime('%Y-%m-%d')

    """
    with create_engine(os.getenv('DB_URL')).connect() as conn:
        try:
            conn.execute(f'DELETE FROM "{ticker}" WHERE DATEDATA >= TO_DATE(\'{start_date}\', \'YYYY-MM-DD\') AND DATEDATA <= TO_DATE(\'{end_date}\', \'YYYY-MM-DD\')')
            #daily_data.to_sql(ticker, conn, if_exists='replace', index=True, index_label=['DATEDATA'], dtype=dtype)
            daily_data.to_sql(ticker, conn, if_exists='append', index=True, index_label=['DATEDATA'], dtype=dtype)
            daily_data = pd.read_sql(f'SELECT DATEDATA, OPEN, HIGH, LOW, CLOSE, VOLUME, VALUE, MARKETCAP FROM "{ticker}" ORDER BY DATEDATA', conn)

        except:
            daily_data.to_sql(ticker, conn, if_exists='replace', index=True, index_label=['DATEDATA'], dtype=dtype)
            daily_data = pd.read_sql(f'SELECT DATEDATA, OPEN, HIGH, LOW, CLOSE, VOLUME, VALUE, MARKETCAP FROM "{ticker}" ORDER BY DATEDATA', conn)
    """    
    daily_data.columns = daily_data.columns.str.upper()
    daily_data.set_index(['DATEDATA'], drop=True, inplace=True)
    daily_data.index = pd.to_datetime(daily_data.index)

    data = pd.merge(daily_data, yearly_data, how='left', left_on=daily_data.index.year, right_on=yearly_data.index)
    
    data['DATEDATA'] = daily_data.index
    data.set_index('DATEDATA', drop=True, inplace=True)
    data.drop(columns=['CLOSE_y'], inplace=True)
    data.rename(columns={'CLOSE_x':'CLOSE', 'key_0':'YEAR'}, inplace=True)
    
    data.replace([np.inf, -np.inf, np.nan], 0, inplace=True)
    daily_adjustment=pd.DataFrame({'DATEDATA': [], 'ADJEPS': [], 'ADJBPS': [], 'ADJDPS': []})
    list_index, list_adjeps, list_adjbps, list_adjdps = [], [], [], []

    for year_index, current_year_data in yearly_data.iterrows() :

        if year_index == datetime.today().year :
            year_length = current_year_length
        else :
            year_length = len(data[data['YEAR']==year_index])

        if (current_year_data.NEXTEPS == 0) or (np.isnan(current_year_data.NEXTEPS)) :
            if (current_year_data.FWD_EPS == 0) or (np.isnan(current_year_data.FWD_EPS)) :
                EPS_daily_adjustment = 0 
            else :
                if (current_year_data.EPS == 0) or (np.isnan(current_year_data.EPS)) :
                    EPS_daily_adjustment = (current_year_data.FWD_EPS - last_EPS) / year_length
                else :
                    EPS_daily_adjustment = (current_year_data.FWD_EPS - current_year_data.EPS) / year_length
        else :
            EPS_daily_adjustment = (current_year_data.NEXTEPS - current_year_data.EPS) / year_length

        if (current_year_data.BPS == 0) or (np.isnan(current_year_data.BPS)) :
            BPS_daily_adjustment = 0
        else :
            if (current_year_data.NEXTBPS == 0) or (np.isnan(current_year_data.NEXTBPS)) :
                if (current_year_data.FWD_EPS == 0) or (np.isnan(current_year_data.FWD_EPS)) :
                    BPS_daily_adjustment = 0
                else :
                    BPS_daily_adjustment = current_year_data.FWD_EPS / year_length
            else :         
                BPS_daily_adjustment = (current_year_data.NEXTBPS - current_year_data.BPS) / year_length

        DPS_daily_adjustment = indicator_daily_adjustment(current_year_data.DPS, current_year_data.NEXTDPS, year_length)

        last_EPS = find_last_value(list_adjeps, current_year_data.EPS)
        last_BPS = find_last_value(list_adjbps, current_year_data.BPS)
        last_DPS = find_last_value(list_adjdps, current_year_data.DPS)

        for data_index, current_data in data[data['YEAR'] == year_index].iterrows() :
            list_index.append(data_index)
            last_EPS = last_EPS + EPS_daily_adjustment
            last_BPS = last_BPS + BPS_daily_adjustment
            last_DPS = last_DPS + DPS_daily_adjustment
            list_adjeps.append(last_EPS)
            list_adjbps.append(last_BPS)
            list_adjdps.append(last_DPS)

    daily_adjustment = pd.DataFrame({'DATEDATA': list_index,
                                    'ADJEPS': list_adjeps, 
                                    'ADJBPS': list_adjbps,
                                    'ADJDPS': list_adjdps})
    daily_adjustment.set_index('DATEDATA', inplace=True)

    data = pd.concat([data, daily_adjustment], axis=1)
    
    data['PER'] = data['CLOSE'] / data['ADJEPS']
    data['PBR'] = data['CLOSE'] / data['ADJBPS']
    data['DBR'] = data['ADJDPS'] / data['CLOSE']

    data.replace([np.inf, -np.inf, np.nan], 0, inplace=True)

    data['PERZ'] = (data['PER'] - data[data['PER'] != 0]['PER'].mean()) / data[data['PER'] != 0]['PER'].std(ddof=0)
    data['PBRZ'] = (data['PBR'] - data[data['PBR'] != 0]['PBR'].mean()) / data[data['PBR'] != 0]['PBR'].std(ddof=0)
    data['DBRZ'] = (data['DBR'] - data[data['DBR'] != 0]['DBR'].mean()) / data[data['DBR'] != 0]['DBR'].std(ddof=0) 
    """    
    with create_engine(os.getenv('DB_URL')).connect() as conn:
        data.to_sql(ticker, conn, if_exists='replace', index=True, index_label=['DATEDATA'])
    """ 
    
    data.drop(columns=['YEAR', 'FWD_PER'], inplace=True)
    data['TICKER'] = ticker
    data.reset_index(inplace=True)
    data.set_index(['DATEDATA','TICKER'], drop=True, inplace=True)
    
    data['NAME'] = stock.get_index_ticker_name(ticker)
    """ 
    with create_engine(os.getenv('DB_URL')).connect() as conn:
        conn.execute(f"DELETE FROM data WHERE TICKER = '{ticker}'")
        data.iloc[-1:].to_sql('data', conn, if_exists='append', index=True, index_label=['DATEDATA', 'TICKER'])
    """ 