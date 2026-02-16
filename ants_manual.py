from ANTS.bot import send_msg_telegram
from ANTS.data import ticker_data_download, etf_data_download
import mojito
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
import requests
warnings.filterwarnings("ignore")
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

load_dotenv()

broker = mojito.KoreaInvestment(
                api_key=os.getenv('KIS_APP_KEY'),
                api_secret=os.getenv('KIS_APP_SECRET'),
                acc_no=os.getenv('KIS_ACCOUNT'),
                mock=False
            )

xcal = xcals.get_calendar("XKRX")
cal=pd.DataFrame({'Date': xcal.schedule.open.apply(lambda x: x.date), 'Year': xcal.schedule.open.apply(lambda x: x.year)})
cal.set_index('Date', drop=True, inplace=True)

currnet_year_length = len(cal[cal['Year']==datetime.today().year])
#currnet_year_length = 260

stocks = pd.concat([fdr.StockListing('KOSPI'), fdr.StockListing('KOSDAQ'), fdr.StockListing('ETF/KR')], ignore_index=True)
etfs = fdr.StockListing('ETF/KR')

total = []
        
for idx, row in stocks.iterrows():
    
    print(f"{idx+1}/{len(stocks)+len(etfs)} : {row['Code']} : {row['Name']}", end=" ")

    try :
        data = ticker_data_download(ticker=row['Code'], current_year_length=currnet_year_length, broker=broker, total='')
        data['MARKETCAP'] = row['Marcap'] / 100000000
        data['NAME'] = row['Name']
        print('Updated')
        if len(total) == 0 :
            total = data
        else :
            total = pd.concat([total, data])

    except :
        print('Fail')

total['NAME'] = total['NAME'].astype(str).str.slice(0, 80)
total['INDUSTRY'] = total['INDUSTRY'].astype(str).str.slice(0, 80)

numeric_cols = ['PER', 'PBR', 'PSR', 'EV_EBITDA',
                'PERZ', 'PBRZ', 'PSRZ', 'EV_EBITDAZ', 'PRICEZ',
                'SALES_GROWTH', 'OP_GROWTH', 'NP_GROWTH', 'MARKETCAP']

total[numeric_cols] = total[numeric_cols].apply(lambda x: pd.to_numeric(x, errors='coerce'))
total[numeric_cols] = total[numeric_cols].fillna(0)
total[numeric_cols] = total[numeric_cols].replace([np.inf, -np.inf], 0)

with create_engine(os.getenv('DB_URL'), use_ansi=True).connect() as conn: 
    total.to_sql('data', conn, if_exists='replace', index=False, dtype=dtype)

# --- Notion DB Update ---
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DATABASE_ID_STOCK = os.getenv('NOTION_DATABASE_ID_STOCK')

if NOTION_TOKEN and NOTION_DATABASE_ID_STOCK :
    headers = {
        "Authorization": "Bearer " + NOTION_TOKEN,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # 1. 데이터베이스의 모든 페이지 삭제 (아카이브)
    query_url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID_STOCK}/query"
    
    pages_to_delete = []
    has_more = True
    next_cursor = None
    while has_more:
        payload = {}
        if next_cursor:
            payload['start_cursor'] = next_cursor
            
        res = requests.post(query_url, headers=headers, json=payload)
        if res.status_code == 200:
            data = res.json()
            pages_to_delete.extend(data['results'])
            has_more = data['has_more']
            next_cursor = data.get('next_cursor')
        else:
            print(f"Notion DB 조회 오류: {res.status_code} {res.text}")
            has_more = False

    for page in pages_to_delete:
        page_id = page['id']
        archive_url = f"https://api.notion.com/v1/pages/{page_id}"
        archive_payload = {"archived": True}
        patch_res = requests.patch(archive_url, headers=headers, json=archive_payload)
        if patch_res.status_code != 200:
            print(f"페이지 보관(archive) 오류 {page_id}: {patch_res.status_code}")
        time.sleep(0.4) # Notion API rate limit (3 req/sec)

    print("Notion 데이터 삭제 완료.")

    # 2. 새로운 데이터 삽입
    print("Notion에 새로운 데이터 삽입 중...")
    create_url = "https://api.notion.com/v1/pages"
    
    for _, row in total.iterrows():
        properties = {}
        # DataFrame의 모든 컬럼을 순회하며 Notion 속성 객체를 생성합니다.
        for col_name in total.columns:
            value = row[col_name]

            # Notion DB의 속성 타입에 맞게 데이터를 포맷팅합니다.
            # 'TICKER' 컬럼을 Notion의 'Title' 타입(Key)으로 처리합니다.
            if col_name == 'TICKER':
                properties[col_name] = {'title': [{'text': {'content': str(value) if pd.notna(value) else ''}}]}
            # numeric_cols 리스트에 있는 컬럼은 'Number' 타입으로 처리합니다.
            elif col_name in numeric_cols:
                properties[col_name] = {'number': round(float(value), 1) if pd.notna(value) else None}
            # 그 외 컬럼(NAME, INDUSTRY 등)은 'Rich Text' 타입으로 처리합니다.
            else:
                properties[col_name] = {'rich_text': [{'text': {'content': str(value) if pd.notna(value) else ''}}]}

        page_data = {"parent": {"database_id": NOTION_DATABASE_ID_STOCK}, "properties": properties}
        
        res = requests.post(create_url, headers=headers, json=page_data)
        if res.status_code != 200:
            print(f"Notion 페이지 생성 오류 (Ticker: {row['TICKER']}): {res.status_code} {res.text}")
        time.sleep(0.4) # Notion API rate limit
    print("Notion 데이터 삽입 완료.")
else:
    print("NOTION_TOKEN 또는 NOTION_DATABASE_ID가 설정되지 않았습니다. Notion 업데이트를 건너뜁니다.")

total = []

for idx, row in etfs.iterrows():
    print(f"{len(stocks)+idx+1}/{len(stocks)+len(etfs)} : {row['Symbol']} : {row['Name']}", end=" ")

    #print(str(idx+1), "/", len(stocks) + len(etfs), " : ", row['Symbol'], end=' ')
    try :
        data = etf_data_download(ticker=row['Symbol'], current_year_length=currnet_year_length, broker=broker, total='')
        data['NAME'] = row['Name']
        data['MARKETCAP'] = row['MarCap']
        data['INDUSTRY'] = 'ETF'
        data['PRICE'] = row['Price']
        data['NAV'] = row['NAV']
        data['PREMIUM'] = (data['PRICE'] - data['NAV']) / data['NAV'] * 100
        data['AMOUNT'] = row['Amount'] 
        print('Updated')

        if len(total) == 0 :
            total = data
        else :
            total = pd.concat([total, data])

    except :
        print('Fail')

numeric_cols = ['PRICEZ', 'PRICE', 'NAV', 'PREMIUM', 'MARKETCAP','AMOUNT']

db_df = total.drop(columns=['PRICE', 'NAV', 'PREMIUM','AMOUNT'], axis=1, inplace=False)
with create_engine(os.getenv('DB_URL'), use_ansi=True).connect() as conn:    
    db_df.to_sql('data', conn, if_exists='append', index=False, dtype=dtype)

# --- Notion DB Update ---
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DATABASE_ID_ETF = os.getenv('NOTION_DATABASE_ID_ETF')

if NOTION_TOKEN and NOTION_DATABASE_ID_ETF :
    headers = {
        "Authorization": "Bearer " + NOTION_TOKEN,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # 1. 데이터베이스의 모든 페이지 삭제 (아카이브)
    query_url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID_ETF}/query"
    
    pages_to_delete = []
    has_more = True
    next_cursor = None
    while has_more:
        payload = {}
        if next_cursor:
            payload['start_cursor'] = next_cursor
            
        res = requests.post(query_url, headers=headers, json=payload)
        if res.status_code == 200:
            data = res.json()
            pages_to_delete.extend(data['results'])
            has_more = data['has_more']
            next_cursor = data.get('next_cursor')
        else:
            print(f"Notion DB 조회 오류: {res.status_code} {res.text}")
            has_more = False

    for page in pages_to_delete:
        page_id = page['id']
        archive_url = f"https://api.notion.com/v1/pages/{page_id}"
        archive_payload = {"archived": True}
        patch_res = requests.patch(archive_url, headers=headers, json=archive_payload)
        if patch_res.status_code != 200:
            print(f"페이지 보관(archive) 오류 {page_id}: {patch_res.status_code}")
        time.sleep(0.4) # Notion API rate limit (3 req/sec)

    print("Notion 데이터 삭제 완료.")

    # 2. 새로운 데이터 삽입
    print("Notion에 새로운 데이터 삽입 중...")
    create_url = "https://api.notion.com/v1/pages"
    
    for _, row in total.iterrows():
        properties = {}
        # DataFrame의 모든 컬럼을 순회하며 Notion 속성 객체를 생성합니다.
        for col_name in total.columns:
            value = row[col_name]

            # Notion DB의 속성 타입에 맞게 데이터를 포맷팅합니다.
            # 'TICKER' 컬럼을 Notion의 'Title' 타입(Key)으로 처리합니다.
            if col_name == 'TICKER':
                properties[col_name] = {'title': [{'text': {'content': str(value) if pd.notna(value) else ''}}]}
            # numeric_cols 리스트에 있는 컬럼은 'Number' 타입으로 처리합니다.
            elif col_name in numeric_cols:
                properties[col_name] = {'number': round(float(value), 1) if pd.notna(value) else None}
            # 그 외 컬럼(NAME, INDUSTRY 등)은 'Rich Text' 타입으로 처리합니다.
            else:
                properties[col_name] = {'rich_text': [{'text': {'content': str(value) if pd.notna(value) else ''}}]}

        page_data = {"parent": {"database_id": NOTION_DATABASE_ID_ETF}, "properties": properties}
        
        res = requests.post(create_url, headers=headers, json=page_data)
        if res.status_code != 200:
            print(f"Notion 페이지 생성 오류 (Ticker: {row['TICKER']}): {res.status_code} {res.text}")
        time.sleep(0.4) # Notion API rate limit
    print("Notion 데이터 삽입 완료.")
else:
    print("NOTION_TOKEN 또는 NOTION_DATABASE_ID가 설정되지 않았습니다. Notion 업데이트를 건너뜁니다.")

send_msg_telegram(os.getenv('TELEGRAM_TOKEN'), os.getenv('TELEGRAM_ID'), 'Data 집계 완료')