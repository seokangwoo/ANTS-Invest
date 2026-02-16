from ANTS.data import ticker_data_download
from ANTS.bot import send_msg_telegram
from pykrx import stock
from ANTS.kis_api import KisApi
# import mojito
import FinanceDataReader as fdr
import exchange_calendars as xcals
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from sqlalchemy import create_engine, types
from dotenv import load_dotenv
import schedule
import time
import os
import warnings

warnings.filterwarnings("ignore")

def job():
    load_dotenv()

    dtype={
        'TICKER': types.VARCHAR(10),
        'NAME': types.VARCHAR(80),
        'INDUSTRY': types.VARCHAR(80),
        'PER': types.FLOAT(),
        'PBR': types.FLOAT(),
        'PSR': types.FLOAT(),
        'EV_EBITDA': types.FLOAT(),
        'PERZ': types.FLOAT(),
        'PBRZ': types.FLOAT(),
        'PSRZ': types.FLOAT(),
        'EV_EBITDAZ': types.FLOAT(),
        'PRICEZ': types.FLOAT(),
        'SALES_GROWTH': types.FLOAT(),
        'OP_GROWTH': types.FLOAT(),
        'NP_GROWTH': types.FLOAT(),
        'MARKETCAP': types.FLOAT(),
    }

    broker = KisApi(
                    api_key=os.getenv('KIS_APP_KEY'),
                    api_secret=os.getenv('KIS_APP_SECRET'),
                    acc_no=os.getenv('KIS_ACCOUNT'),
                    mock=False
                )

    xcal = xcals.get_calendar("XKRX")
    cal=pd.DataFrame({'Date': xcal.schedule.open.apply(lambda x: x.date), 'Year': xcal.schedule.open.apply(lambda x: x.year)})
    cal.set_index('Date', drop=True, inplace=True)
    print(cal)

    current_year_length = len(cal[cal['Year']==datetime.today().year])

    stocks = pd.concat([fdr.StockListing('KOSPI'), fdr.StockListing('KOSDAQ')], ignore_index=True)
    ticker_list = stocks['Code'].tolist()
    stocks.set_index('Code', inplace=True)

    i=1
    total = pd.DataFrame()
            
    for ticker in ticker_list :
        #print(i, "/", len(ticker_list)+1, " : ", ticker, end=' ')
        #i = i + 1
        try :
            data = ticker_data_download(ticker=ticker, current_year_length=current_year_length, broker=broker, total='')
            data['MARKETCAP'] = stocks.loc[ticker]['Marcap'] / 100000000

            #print('Updated')
            if len(total) == 0 :
                total = data
            elif len(data) != 0 :
                total = pd.concat([total, data])

        except Exception as e: print(f"Error {ticker}: {e}")


        except Exception as e: print(f"Error {ticker}: {e}")

        # time.sleep(0.5) # Removed for performance
    
    try :
        total['NAME'] = total['NAME'].astype(str).str.slice(0, 80)
        total['INDUSTRY'] = total['INDUSTRY'].astype(str).str.slice(0, 80)
    except Exception as e: print(f"Error {ticker}: {e}")
    
    numeric_cols = ['PER', 'PBR', 'PSR', 'EV_EBITDA',
                'PERZ', 'PBRZ', 'PSRZ', 'EV_EBITDAZ', 'PRICEZ',
                'SALES_GROWTH', 'OP_GROWTH', 'NP_GROWTH', 'MARKETCAP']

    total[numeric_cols] = total[numeric_cols].apply(lambda x: pd.to_numeric(x, errors='coerce'))
    total[numeric_cols] = total[numeric_cols].fillna(0)
    total[numeric_cols] = total[numeric_cols].replace([np.inf, -np.inf], 0)
    
    # Remove use_ansi=True which is for Oracle
    with create_engine(os.getenv('DB_URL')).connect() as conn:
        
        total.to_sql('data', conn, if_exists='replace', index=False, dtype=dtype)

    send_msg_telegram(os.getenv('TELEGRAM_TOKEN'), os.getenv('TELEGRAM_ID'), 'Data 집계 완료')
    # broker.revoke_access_token() # Not implemented/needed for KisApi custom wrapper currently

schedule.every().monday.at('18:10').do(job)
schedule.every().tuesday.at('18:10').do(job)
schedule.every().wednesday.at('18:10').do(job)
schedule.every().thursday.at('18:10').do(job)
schedule.every().friday.at('18:10').do(job)

while True:
    schedule.run_pending()
    time.sleep(1)