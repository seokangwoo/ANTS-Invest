import pandas as pd
import numpy as np
from datetime import datetime, timedelta
# import mojito # Removed
import FinanceDataReader as fdr
# from sqlalchemy import create_engine, types
from sklearn.linear_model import LinearRegression
from dotenv import load_dotenv
import os

def get_daily_data(ticker: str, timeframe: str, start_date: str, end_date: str, broker) :
    # Switch to FinanceDataReader for speed (No 100-item limit)
    # broker arg is unused but kept for compatibility
    
    # Convert YYYYMMDD to YYYY-MM-DD for consistency (FDR handles both but let's be safe)
    # Actually FDR handles strings fine.
    
    try:
        data = fdr.DataReader(ticker, start=start_date, end=end_date)
        
        if data.empty:
            return pd.DataFrame()
            
        # FDR returns index=Date. Reset to make it a column for consistency with rest of code logic
        data = data.reset_index()
        
        # Rename columns to match expected format: 
        # FDR KRX cols: Date, Open, High, Low, Close, Volume, Change
        # We need: Date, Open, High, Low, Close, Volume
        
        # Standardize column names
        data.columns = [c.capitalize() for c in data.columns]
        
        # Ensure 'Date' column exists (reset_index creates 'Date' usually)
        if 'Date' not in data.columns and 'Index' in data.columns:
             data.rename(columns={'Index': 'Date'}, inplace=True)
             
        # Select required columns
        req_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        data = data[req_cols]
        
        return data
        
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()

    return data

def find_last_value(list_adjvalue:list, current_year_data) :
    # Helper to clean nan
    def is_valid(val):
        return pd.notna(val) and val != 0

    if len(list_adjvalue) > 0 :
        # If last calculated value is valid, use it.
        # If last calculated value is 0 or nan, check current year.
        last_calc = list_adjvalue[-1]
        
        if not is_valid(last_calc) :
            if not is_valid(current_year_data) : last_value = np.nan # Propagate NaN
            else : last_value = current_year_data
        else : 
             last_value = last_calc
    else :
        # First entry
        if not is_valid(current_year_data) : last_value = np.nan
        else : last_value = current_year_data
        
    # If last_value is NaN, treat as 0 for calculations? 
    # Or keep as NaN -> then subsequent adds will be NaN.
    # If we want 0, return 0. If we want gap, return NaN.
    # The original logic seemed to treat 0 as "no data to propagate".
    # For chart, NaN is better.
    return last_value

def ticker_data_download(ticker: str, current_year_length: int, broker, total) :

    resp = broker.fetch_financial_ratio(symbol=ticker, timeframe='Y')
    financial_ratio = pd.DataFrame(resp.get('output', []))
    
    # Ensure expected columns exist even if empty
    expected_cols = ['stac_yymm', 'eps', 'sps', 'bps']
    for col in expected_cols:
        if col not in financial_ratio.columns:
            financial_ratio[col] = np.nan
            
    financial_ratio = financial_ratio[['stac_yymm', 'eps', 'sps', 'bps']]
    financial_ratio.rename(columns={'stac_yymm': 'YEAR', 'eps': 'EPS', 'sps': 'SPS', 'bps': 'BPS'}, inplace=True)
    
    # Ensure YEAR is string for .str accessor
    financial_ratio['YEAR'] = financial_ratio['YEAR'].astype(str)
    
    # OLD: financial_ratio = financial_ratio[financial_ratio['YEAR'].str.endswith('12')]
    # NEW: Keep full year (first 4 chars) and drop duplicates (keep first/latest)
    financial_ratio['YEAR'] = financial_ratio['YEAR'].str[:4]
    financial_ratio = financial_ratio.drop_duplicates(subset=['YEAR'], keep='first')
    
    financial_ratio.set_index(['YEAR'], drop=True, inplace=True)

    resp = broker.fetch_other_major_ratios(symbol=ticker, timeframe='Y')
    other_major_ratios = pd.DataFrame(resp.get('output', []))
    
    expected_cols_other = ['stac_yymm', 'ebitda', 'ev_ebitda']
    for col in expected_cols_other:
        if col not in other_major_ratios.columns:
            other_major_ratios[col] = np.nan

    other_major_ratios = other_major_ratios[['stac_yymm', 'ebitda', 'ev_ebitda']]
    other_major_ratios.rename(columns={'stac_yymm': 'YEAR', 'ebitda': 'EBITDA', 'ev_ebitda': 'EV_EBITDA'}, inplace=True)
    
    # Ensure YEAR is string
    other_major_ratios['YEAR'] = other_major_ratios['YEAR'].astype(str)
    
    other_major_ratios['YEAR'] = other_major_ratios['YEAR'].str[:4]
    other_major_ratios = other_major_ratios.drop_duplicates(subset=['YEAR'], keep='first')
    
    other_major_ratios.set_index(['YEAR'], drop=True, inplace=True)

    yearly_data = pd.concat([financial_ratio, other_major_ratios], axis=1, join='outer')

    resp = broker.search_stock_info(symbol=ticker)
    out = resp.get('output', {})
    try:
        share = pd.to_numeric(out.get('lstg_stqt', '1')) # Default 1 if missing
        name = out.get('prdt_abrv_name', ticker)
        industry = out.get('idx_bztp_mcls_cd_name', 'Unknown')
    except:
        share = 1
        name = ticker
        industry = 'Unknown'

    # Ensure yearly_data index is integer YEAR before forecast logic
    yearly_data.index = pd.to_datetime(yearly_data.index, format='%Y').year
    # Clean Index (Drop NaNs, Ensure Int) to prevent RangeIndex errors
    yearly_data = yearly_data[pd.notnull(yearly_data.index)]
    yearly_data.index = yearly_data.index.astype(int)
    
    yearly_data.sort_index(inplace=True)

    try : 
        resp = broker.fetch_estimate_perform(symbol=ticker)
        # Check if keys exist
        if 'output2' not in resp or 'output3' not in resp or 'output4' not in resp:
            raise Exception("Missing Forecast Data")
            
        output2 = pd.DataFrame(resp['output2'])
        output3 = pd.DataFrame(resp['output3'])
        output4 = pd.DataFrame(resp['output4'])

        output2.rename(columns={'data1': output4.iloc[0, 0][:4], 'data2': output4.iloc[1, 0][:4], 'data3': output4.iloc[2, 0][:4], 'data4': output4.iloc[3, 0][:4], 'data5': output4.iloc[4, 0][:4]}, inplace=True)
        sales_growth = float(output2.T.loc[str(datetime.now().year+1)][1]) / 10
        op_growth = float(output2.T.loc[str(datetime.now().year+1)][3]) / 10
        np_growth = float(output2.T.loc[str(datetime.now().year+1)][5]) / 10
        output2 = output2.T[[0,4]]
        output2.rename(columns={0:'sales_f',4:'profit_f'}, inplace=True)

        output3.rename(columns={'data1': output4.iloc[0, 0][:4], 'data2': output4.iloc[1, 0][:4], 'data3': output4.iloc[2, 0][:4], 'data4': output4.iloc[3, 0][:4], 'data5': output4.iloc[4, 0][:4]}, inplace=True)
        output3 = output3.T[[0, 1, 4]]
        output3.rename(columns={0:'EBITDA_f',1:'EPS_f',4:'EV_EBITDA_f'}, inplace=True)

        forecast = pd.concat([output3, output2], axis=1, join='outer')
        # forecast index needs to be int year
        forecast.index = pd.to_numeric(forecast.index)

        yearly_data = pd.concat([yearly_data, forecast], axis=1, join='outer')
        yearly_data.sort_index(inplace=True)
        yearly_data = yearly_data.apply(pd.to_numeric, errors='coerce')

        for idx, row in yearly_data[yearly_data['EBITDA'].isna()].iterrows():
            yearly_data.at[idx, 'EPS'] = row['EPS_f'] / 10
            yearly_data.at[idx, 'EBITDA'] = row['EBITDA_f']
            yearly_data.at[idx, 'EV_EBITDA'] = row['EV_EBITDA_f'] / 10
            yearly_data.at[idx, 'SPS'] = row['sales_f'] * 100000000 / share
            yearly_data.at[idx, 'BPS'] = yearly_data.loc[idx-1]['BPS'] + row['profit_f'] * 100000000 / share
            yearly_data = yearly_data[['EPS', 'SPS', 'BPS','EBITDA','EV_EBITDA']]
        
    except Exception as e:
        # print(f"Forecast Error: {e}") 
        yearly_data = yearly_data.apply(pd.to_numeric, errors='coerce')
        yearly_data.sort_index(inplace=True)

    # --- FIX START ---
    # Drop rows where Index (Year) is NaN (failed parse)
    yearly_data = yearly_data[pd.notnull(yearly_data.index)]
    # Convert index to int (to avoid float index with 2024.0)
    yearly_data.index = yearly_data.index.astype(int)
    # --- FIX END ---
    
    yearly_data.sort_index(inplace=True)

    # --- Unified Extension Logic (Runs for both Success and Failure) ---
    # Ensure we cover up to target year (Next Year)
    if not yearly_data.empty:
        max_year = int(yearly_data.index.max())
        current_year = datetime.now().year
        target_year = current_year + 1 # e.g. 2026+1 = 2027 (Next Year)
        
        # If max_year is less than target_year, we forward fill
        if max_year < target_year:
            last_row = yearly_data.loc[max_year]
            for y in range(max_year + 1, target_year + 1): 
                yearly_data.loc[y] = last_row

    # Ensure continuous years (Interpolate gaps, e.g. between History and Forecast)
    if not yearly_data.empty:
        min_year = int(yearly_data.index.min())
        max_year = int(yearly_data.index.max())
        full_range = range(min_year, max_year + 1)
        yearly_data = yearly_data.reindex(full_range).interpolate(method='linear')
        yearly_data = yearly_data.ffill().bfill() # Safe fill edges

    yearly_data['EV'] = yearly_data['EBITDA'] * yearly_data['EV_EBITDA']

    yearly_data['NEXT_EPS'] = yearly_data['EPS'].shift(-1)
    yearly_data['NEXT_SPS'] = yearly_data['SPS'].shift(-1)
    yearly_data['NEXT_BPS'] = yearly_data['BPS'].shift(-1)
    yearly_data['NEXT_EBITDA'] = yearly_data['EBITDA'].shift(-1)
    yearly_data['NEXT_EV_EBITDA'] = yearly_data['EV_EBITDA'].shift(-1)
    yearly_data['NEXT_EV'] = yearly_data['NEXT_EBITDA'] * yearly_data['NEXT_EV_EBITDA']

    # Define fetch range (Fetch ALL data as requested)
    end_dt = datetime.now()
    start_dt = datetime(1990, 1, 1) # Start from 1990 for full history
    end_str = end_dt.strftime('%Y%m%d')
    start_str = start_dt.strftime('%Y%m%d')

    # Fetch daily data using KIS API
    daily_data = get_daily_data(ticker, 'D', start_str, end_str, broker)
    
    # KIS get_daily_data returns columns: Date, Open, High, Low, Close, Volume
    # Ensure types are numeric
    cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for c in cols:
        daily_data[c] = pd.to_numeric(daily_data[c])
    
    # daily_data index is not set in get_daily_data?
    # get_daily_data returns default index. 'Date' is a column.
    
    daily_data['DATE'] = pd.to_datetime(daily_data['Date'])
    daily_data.drop(columns=['Date', 'Volume'], inplace=True) # match previous fdr behavior (dropped Volume)
    
    # Previous fdr code:
    # daily_data.columns = daily_data.columns.str.upper() => OPEN, HIGH, LOW, CLOSE
    # daily_data["DATEINDEX"] = daily_data['DATE']
    # daily_data = daily_data.set_index(['DATEINDEX'])
    
    daily_data.columns = daily_data.columns.str.upper()
    daily_data["DATEINDEX"] = daily_data['DATE']
    daily_data = daily_data.set_index(['DATEINDEX'])
    
    daily_data = daily_data.sort_index() # Ensure sorted by date
    
    # Drop rows where index is NaT or Date is NaT
    daily_data = daily_data[pd.notnull(daily_data.index)]
    
    # Check for NaNs in CLOSE and fill if necessary
    if daily_data['CLOSE'].isnull().any():
        daily_data['CLOSE'] = daily_data['CLOSE'].ffill()
        
    # Also drop rows where CLOSE is still NaN (e.g. at the start)
    daily_data = daily_data.dropna(subset=['CLOSE'])

    first_close_per_year = daily_data.groupby(daily_data.index.year).first()[['CLOSE']].rename(columns={'CLOSE': 'first_close'})
    yearly_data = yearly_data.join(first_close_per_year)
    yearly_data['DEBT_CASH'] = yearly_data['first_close'] * share / 100000000 - yearly_data['EV']
    yearly_data['NEXT_DEBT_CASH'] = yearly_data['DEBT_CASH'].shift(-1)

    yearly_data['NEXT_EPS'] = yearly_data['NEXT_EPS'].fillna(yearly_data['EPS'])
    yearly_data['NEXT_SPS'] = yearly_data['NEXT_SPS'].fillna(yearly_data['SPS'])
    yearly_data['NEXT_BPS'] = yearly_data['NEXT_BPS'].fillna(yearly_data['BPS'])
    yearly_data['NEXT_EBITDA'] = yearly_data['NEXT_EBITDA'].fillna(yearly_data['EBITDA'])
    yearly_data['NEXT_DEBT_CASH'] = yearly_data['NEXT_DEBT_CASH'].fillna(yearly_data['DEBT_CASH'])

    # Refactored Merge: Explicit Column + Right Index
    daily_data['YEAR'] = daily_data.index.year
    data = pd.merge(daily_data, yearly_data, how='left', left_on='YEAR', right_index=True)
    # data.rename(columns={'key_0':'YEAR'}, inplace=True) # Year col already exists from daily_data
    #data = data.dropna()
    data.set_index('DATE', drop=True, inplace=True)
    
    list_index, list_adj_eps, list_adj_bps, list_adj_sps, list_adj_ebitda, list_adj_debt_cash = [], [], [], [], [], []

    for year_index, current_year_data in yearly_data.iterrows() :
        if year_index == datetime.today().year :
            year_length = current_year_length
        else :
            year_length = len(data[data['YEAR']==year_index])
    
        if year_length > 0:
            eps_daily_adjustment = (current_year_data.NEXT_EPS - current_year_data.EPS) / year_length
            bps_daily_adjustment = (current_year_data.NEXT_BPS - current_year_data.BPS) / year_length
            sps_daily_adjustment = (current_year_data.NEXT_SPS - current_year_data.SPS) / year_length
            ebitda_daily_adjustment = (current_year_data.NEXT_EBITDA - current_year_data.EBITDA) / year_length
            debt_cash_daily_adjustment = (current_year_data.NEXT_DEBT_CASH - current_year_data.DEBT_CASH) / year_length
        else:
            eps_daily_adjustment = 0
            bps_daily_adjustment = 0
            sps_daily_adjustment = 0
            ebitda_daily_adjustment = 0
            debt_cash_daily_adjustment = 0

        last_eps = find_last_value(list_adj_eps, current_year_data.EPS)
        last_bps = find_last_value(list_adj_bps, current_year_data.BPS)
        last_sps = find_last_value(list_adj_sps, current_year_data.SPS)
        last_ebitda = find_last_value(list_adj_ebitda, current_year_data.EBITDA)
        last_debt_cash = find_last_value(list_adj_debt_cash, current_year_data.DEBT_CASH)

        for data_index, current_data in data[data['YEAR'] == year_index].iterrows() :
            list_index.append(data_index)
            last_eps = last_eps + eps_daily_adjustment
            last_bps = last_bps + bps_daily_adjustment
            last_sps = last_sps + sps_daily_adjustment
            last_ebitda = last_ebitda + ebitda_daily_adjustment
            last_debt_cash = last_debt_cash + debt_cash_daily_adjustment

            list_adj_eps.append(last_eps)
            list_adj_bps.append(last_bps)
            list_adj_sps.append(last_sps)
            list_adj_ebitda.append(last_ebitda)
            list_adj_debt_cash.append(last_debt_cash)

    daily_adjustment = pd.DataFrame({'DATE': list_index,
                                    'ADJ_EPS': list_adj_eps, 
                                    'ADJ_BPS': list_adj_bps,
                                    'ADJ_SPS': list_adj_sps,
                                    'ADJ_EBITDA': list_adj_ebitda,
                                    'ADJ_DEBT_CASH': list_adj_debt_cash}) 

    daily_adjustment.set_index('DATE', inplace=True)
    data = pd.concat([data, daily_adjustment], axis=1)
    data['SHARE'] = share / 100000000
    data['PER'] = data['CLOSE'] / data['ADJ_EPS']
    data['PBR'] = data['CLOSE'] / data['ADJ_BPS']
    data['PSR'] = data['CLOSE'] / data['ADJ_SPS']
    data['EV_EBITDA'] = (data['CLOSE'] * data['SHARE'] - data['ADJ_DEBT_CASH']) / data['ADJ_EBITDA'] 

    data['PERZ'] = (data['PER'] - data[data['PER'] != 0]['PER'].mean()) / data[data['PER'] != 0]['PER'].std(ddof=0)
    data['PBRZ'] = (data['PBR'] - data[data['PBR'] != 0]['PBR'].mean()) / data[data['PBR'] != 0]['PBR'].std(ddof=0)
    data['PSRZ'] = (data['PSR'] - data[data['PSR'] != 0]['PSR'].mean()) / data[data['PSR'] != 0]['PSR'].std(ddof=0)
    data['EV_EBITDAZ'] = (data['EV_EBITDA'] - data[data['EV_EBITDA'] != 0]['EV_EBITDA'].mean()) / data[data['EV_EBITDA'] != 0]['EV_EBITDA'].std(ddof=0)

    data = data.reset_index() 

    model = LinearRegression()
    model.fit(data.index.values.reshape(-1, 1), data['CLOSE'])
    
    data['BASE'] = model.predict(data.index.values.reshape(-1, 1))
    data['Residuals'] = data['CLOSE'] - data['BASE']
    std_dev = data['Residuals'].std()
    data['PRICEZ'] = data['Residuals'] / std_dev

    data.set_index('DATE', drop=True, inplace=True)

    data['TICKER'] = ticker
    data['NAME'] = name
    data['INDUSTRY'] = industry

    try :
        data['SALES_GROWTH'] = sales_growth
        data['OP_GROWTH'] = op_growth
        data['NP_GROWTH'] = np_growth
    except :
        data['SALES_GROWTH'] = 0
        data['OP_GROWTH'] = 0
        data['NP_GROWTH'] = 0
    
    if total == 'X' :
        return data
    else :
        data = data[['TICKER','NAME','INDUSTRY','PER','PBR','PSR','EV_EBITDA','PERZ','PBRZ','PSRZ','EV_EBITDAZ','PRICEZ','SALES_GROWTH','OP_GROWTH','NP_GROWTH']].iloc[-1:]
    return data

def etf_data_download(ticker: str, current_year_length: int, broker, total) :

    data = fdr.DataReader(ticker)
    if len(data) != 0 :
        data = data[(data['Close'] != 0) & (data['Volume'] != 0)]
    data = data.reset_index() 
    data.columns = data.columns.str.upper()

    model = LinearRegression()
    model.fit(data.index.values.reshape(-1, 1), data['CLOSE'])
    
    data['BASE'] = model.predict(data.index.values.reshape(-1, 1))
    data['Residuals'] = data['CLOSE'] - data['BASE']
    std_dev = data['Residuals'].std()
    data['PRICEZ'] = data['Residuals'] / std_dev

    data.set_index('DATE', drop=True, inplace=True)

    data['TICKER'] = ticker
    
    
    if total == 'X' :
        return data
    else :
        data = data[['TICKER','PRICEZ']].iloc[-1:]
    
    return data    