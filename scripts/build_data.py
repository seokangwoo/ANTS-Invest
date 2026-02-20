import sys
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
import FinanceDataReader as fdr
# import mojito

# Add project root to sys.path to import ANTS modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ANTS.data import ticker_data_download, etf_data_download
from ANTS.kis_api import KisApi

# Load environment variables
load_dotenv()

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.strftime('%Y-%m-%d')
    if isinstance(obj, (np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.float64, np.float32)):
        if np.isnan(obj) or np.isinf(obj):
            return 0 # Or None, but 0 is safer for charts/tables expecting numbers
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError ("Type %s not serializable" % type(obj))

def clean_nan(value):
    if isinstance(value, float):
        if np.isnan(value) or np.isinf(value):
            return 0
    return value

def main():
    print("Starting data build...")
    
    # Setup Broker
    # Note: For GitHub Actions, we'll need these env vars set in Secrets
    key = os.getenv('KIS_APP_KEY')
    secret = os.getenv('KIS_APP_SECRET')
    acc_no = os.getenv('KIS_ACCOUNT')
    
    if not key or not secret or not acc_no:
        print("Warning: KIS API credentials not found. Some data sourcing might fail.")

    broker = KisApi(
        api_key=key,
        api_secret=secret,
        acc_no=acc_no,
        mock=False
    )
    
    # Check Auth
    print(f"KIS Broker Initialized. Access Token present: {bool(broker.access_token)}")
    if not broker.access_token:
        print("CRITICAL: KIS Auth Failed. No Access Token. KIS calls will fail.")
    else:
        print("KIS Auth Success. Proceeding.")

    # 1. Get Stock List (KOSPI, KOSDAQ)
    print("Fetching stock list from FinanceDataReader...")
    try:
        # PRODUCTION: Fetch Real List via FDR
        kospi = fdr.StockListing('KOSPI')
        kosdaq = fdr.StockListing('KOSDAQ')
        
        # Robust Column Selection
        expected_cols = ['Code', 'Name', 'Sector', 'Marcap']
        
        # Helper to standardize columns
        def prepare_df(df):
            # Check for alternative column names if needed (e.g., 'Industry')
            if 'Industry' in df.columns and 'Sector' not in df.columns:
                df['Sector'] = df['Industry']
            
            # Debug columns
            print(f"DEBUG: FDR Columns: {df.columns.tolist()}")
            
            # Map alternative names
            if 'Marcap' not in df.columns:
                 if 'MarketCap' in df.columns: df['Marcap'] = df['MarketCap']
                 elif 'Marow' in df.columns: df['Marcap'] = df['Marrow'] # Typos
                 elif 'CmpMktCap' in df.columns: df['Marcap'] = df['CmpMktCap']

            # Select available only
            available = [c for c in expected_cols if c in df.columns]
            out = df[available].copy()
            
            # Fill missing
            for c in expected_cols:
                if c not in out.columns:
                    if c == 'Code': out[c] = ''
                    elif c == 'Name': out[c] = 'Unknown'
                    elif c == 'Sector': out[c] = 'Unknown'
                    elif c == 'Marcap': out[c] = 0
            return out

        ks_stocks = prepare_df(kospi)
        kd_stocks = prepare_df(kosdaq)
        
        stocks = pd.concat([ks_stocks, kd_stocks], ignore_index=True)
        print(f"Fetched {len(stocks)} stocks from KOSPI/KOSDAQ")
        
        # Validation
        if len(stocks) < 50:
             raise Exception("FDR returned too few stocks (<50)")
             
    except Exception as e:
        print(f"Failed to fetch KRX list via FDR: {e}")
        print("CRITICAL: FDR fetch failed. Attempting KIS API Master Download...")
        
        try:
            # KIS API Fallback
            ks = broker.fetch_kospi_master()
            kd = broker.fetch_kosdaq_master()
            
            if ks.empty and kd.empty:
                raise Exception("KIS Master Download Failed")
            
            # Standardize Columns
            # KIS Master returns: 'Code', 'Name', 'DK_Marcap' (in 100M or 100000000? Sample says '억' (100M). Verify later)
            # We treat DK_Marcap as Marcap.
            
            def adapt_kis(df):
                if df.empty: return pd.DataFrame()
                out = df[['Code', 'Name', 'DK_Marcap']].copy()
                out.columns = ['Code', 'Name', 'Marcap']
                # DK_Marcap is likely in 100 Million units (억).
                # ANTS logic expects raw value? OR 100M?
                # In main logic: marcap = float(row.get('Marcap', 0)) -> Deprecated
                # But for sorting, we need comparable values.
                # Let's assume it is 100M unit (e.g. 4000000 = 400 Trillion).
                # Multiplier handled in build loop? 
                # 'Marcap' column in stocks df is mainly used for SORTING.
                return out

            stocks = pd.concat([adapt_kis(ks), adapt_kis(kd)], ignore_index=True)
            print(f"Fetched {len(stocks)} stocks via KIS API Fallback.")
            
        except Exception as e2:
            print(f"KIS API Fallback Failed: {e2}")
            print("Using Hardcoded Top 20 Fallback.")
            # Fallback List (Top Market Cap as of Late 2025/Early 2026)
            fallback_data = [
                {'Code': '005930', 'Name': '삼성전자', 'Sector': '전기전자', 'Marcap': 400000000000000},
                {'Code': '000660', 'Name': 'SK하이닉스', 'Sector': '전기전자', 'Marcap': 140000000000000},
                {'Code': '373220', 'Name': 'LG에너지솔루션', 'Sector': '전기전자', 'Marcap': 90000000000000},
                {'Code': '207940', 'Name': '삼성바이오로직스', 'Sector': '의약품', 'Marcap': 60000000000000},
                {'Code': '005380', 'Name': '현대차', 'Sector': '운수장비', 'Marcap': 50000000000000},
                {'Code': '000270', 'Name': '기아', 'Sector': '운수장비', 'Marcap': 40000000000000},
                {'Code': '005490', 'Name': 'POSCO홀딩스', 'Sector': '철강금속', 'Marcap': 35000000000000},
                {'Code': '035420', 'Name': 'NAVER', 'Sector': '서비스업', 'Marcap': 30000000000000},
                {'Code': '068270', 'Name': '셀트리온', 'Sector': '의약품', 'Marcap': 30000000000000},
                {'Code': '006400', 'Name': '삼성SDI', 'Sector': '전기전자', 'Marcap': 25000000000000},
                {'Code': '051910', 'Name': 'LG화학', 'Sector': '화학', 'Marcap': 25000000000000},
                {'Code': '035720', 'Name': '카카오', 'Sector': '서비스업', 'Marcap': 20000000000000},
                {'Code': '105560', 'Name': 'KB금융', 'Sector': '금융업', 'Marcap': 20000000000000},
                {'Code': '012330', 'Name': '현대모비스', 'Sector': '운수장비', 'Marcap': 20000000000000},
                {'Code': '028260', 'Name': '삼성물산', 'Sector': '유통업', 'Marcap': 20000000000000},
                {'Code': '055550', 'Name': '신한지주', 'Sector': '금융업', 'Marcap': 20000000000000},
                {'Code': '003550', 'Name': 'LG', 'Sector': '기타금융', 'Marcap': 12000000000000},
                {'Code': '032830', 'Name': '삼성생명', 'Sector': '보험', 'Marcap': 12000000000000},
                {'Code': '086790', 'Name': '하나금융지주', 'Sector': '금융업', 'Marcap': 12000000000000},
                {'Code': '000810', 'Name': '삼성화재', 'Sector': '보험', 'Marcap': 12000000000000},
            ]
            stocks = pd.DataFrame(fallback_data)

    # 2. Get ETF List
    print("Fetching ETF list...")
    try:
        etfs_kr = fdr.StockListing("ETF/KR")
        # Ensure 'Symbol', 'Name'
        etfs = etfs_kr[['Symbol', 'Name']].copy()
        # etfs = etfs.head(10) # Limited to 10 for testing
        # etfs = etfs.head(20) # Remove limit for production


        
    except Exception as e:
        print(f"Failed to fetch ETF list: {e}")
        etfs = pd.DataFrame()

    all_tickers_summary = []
    
    # Ensure output directories exist
    os.makedirs('public/data/details', exist_ok=True)

    # Limit to Top 200 for speed test?
    # Or just sort and do all.
    # User complained "Too slow", so maybe Top 500 is a good "Quick" version effectively covering market.
    # Let's Sort by Marcap Descending
    # Limit to Top 10 for Testing (User Request)
    # Limit to Top 20 for Testing (User Request)
    # Limit to Top 20 for Testing
    # Filter out ETFs from stocks
    if not etfs.empty and 'Code' in stocks.columns:
        etf_codes = etfs['Symbol'].unique()
        stocks = stocks[~stocks['Code'].isin(etf_codes)]
        print(f"Filtered out ETFs. Remaining stocks: {len(stocks)}")

    if 'Marcap' in stocks.columns:
        # Clean commas if string
        if stocks['Marcap'].dtype == object:
            stocks['Marcap'] = stocks['Marcap'].astype(str).str.replace(',', '')
        stocks['Marcap'] = pd.to_numeric(stocks['Marcap'], errors='coerce').fillna(0)
        stocks = stocks.sort_values(by='Marcap', ascending=False)
    
    # Enable Full list
    # stocks = stocks.head(10) # Limited to 10 for testing
    
    print(f"Processing {len(stocks)} stocks (KOSPI/KOSDAQ)...")

    def process_stock(row, broker):
        ticker = row['Code']
        name = row['Name']
        sector = row.get('Sector', 'Unknown')
        try:
            # marcap = float(row.get('Marcap', 0)) # Deprecated: Hardcoded/KRX list
            pass
        except:
            marcap = 0
            
        # 0. Fetch Snapshot Data (Price, Marcap, PER, PBR) FIRST
        # User requested API-based Marcap.
        snapshot_data = {}
        try:
            price_detail = broker.fetch_price_detail(ticker)
            if price_detail and 'output' in price_detail:
                snapshot_data = price_detail['output']
                
            # Market Cap (hts_avls) is in 100 Million units
            hts_avls = float(snapshot_data.get('hts_avls', 0))
            if hts_avls > 0:
                marcap = hts_avls * 100000000
                
            # Dynamic Sector Update (if unknown)
            if sector == 'Unknown':
                # bstp_kor_isnm : Sector Name
                api_sector = snapshot_data.get('bstp_kor_isnm', '')
                if api_sector:
                    sector = api_sector
                    # Also update final_industry logic later
                    
        except Exception as e:
            print(f"Error fetching snapshot for {ticker}: {e}")
            marcap = 0
        
        try:
            print(f"Processing {ticker} - {name}...", end=" ")
            current_year_length = 250 
            df = ticker_data_download(ticker=ticker, current_year_length=current_year_length, broker=broker, total='X')
            
            if df is None or df.empty:
                print("Empty Data")
                return None

            # Get Last Row first
            last_row = df.iloc[-1]

            # Calculate Real Market Cap (Price * Shares)
            # SHARE is in 100 million units in ANTS/data.py
            try:
                close_price = float(last_row.get('CLOSE', 0))
                shares_100m = float(last_row.get('SHARE', 0))
                if close_price > 0 and shares_100m > 0:
                    marcap = close_price * shares_100m * 100000000
            except:
                pass

            # Fallback: Fetch Snapshot Data if Calculated values are missing
            snapshot_per = 0
            snapshot_pbr = 0
            
            calc_per = clean_nan(last_row.get('PER', 0))
            calc_pbr = clean_nan(last_row.get('PBR', 0))
            
            # --- FDR Update: Use FDR data if available (Robust Fallback) ---
            fdr_per = float(row.get('PER', 0) if pd.notnull(row.get('PER')) else 0)
            fdr_pbr = float(row.get('PBR', 0) if pd.notnull(row.get('PBR')) else 0)
            fdr_sector = str(row.get('Sector', 'Unknown'))
            if fdr_sector == 'nan': fdr_sector = 'Unknown'
            
            if calc_per == 0: calc_per = fdr_per
            if calc_pbr == 0: calc_pbr = fdr_pbr
            
            target_industry = row.get('Sector', 'Unknown')
            if target_industry == 'Unknown' or pd.isna(target_industry) or target_industry == 'nan':
                 target_industry = fdr_sector
            # -------------------------------------------------------------
            
            # Debug prints removed

            # Fallback to Snapshot values if history calc failed
            if calc_per == 0 and snapshot_data:
                calc_per = float(snapshot_data.get('per', 0))
            if calc_pbr == 0 and snapshot_data:
                calc_pbr = float(snapshot_data.get('pbr', 0))


            # Use FDR Sector if 'Unknown' or missing
            final_industry = clean_nan(last_row.get('INDUSTRY', 'Unknown'))
            if final_industry == 'Unknown' or final_industry == 0:
                 final_industry = sector # Use the (potentially updated) sector from snapshot
                 
            # If still unknown, try target_industry (from initial list)
            if final_industry == 'Unknown':
                 final_industry = target_industry

            # Save Detail JSON
            # last_row already defined above
            # Current Price for Summary
            current_price = 0
            try:
                current_price = float(last_row.get('CLOSE', 0))
            except:
                pass

            try:
                consensus_dir = f"public/data/kr/Consensus"
                if not os.path.exists(consensus_dir):
                    os.makedirs(consensus_dir)
                
                # Initialize variables to avoid UnboundLocalError
                avg_target = 0
                upside = 0
                
                consensus_res = broker.fetch_invest_opbysec(ticker)
                
                if consensus_res and 'output' in consensus_res:
                    consensus_data = consensus_res['output']
                    # Save if valid
                    if consensus_data:
                        with open(f"{consensus_dir}/{ticker}.json", 'w', encoding='utf-8') as f:
                            json.dump(consensus_data, f, ensure_ascii=False, indent=2)
                        
                        # Calculate Average Target Price (Latest per Firm)
                        latest_by_firm = {}
                        for item in consensus_data:
                            try:
                                firm = item.get('mbcr_name')
                                date = item.get('stck_bsop_date') # YYYYMMDD
                                t = float(item.get('hts_goal_prc', 0))
                                
                                if not firm or t <= 0:
                                    continue
                                
                                if firm not in latest_by_firm:
                                    latest_by_firm[firm] = {'date': date, 'target': t}
                                else:
                                    if date > latest_by_firm[firm]['date']:
                                        latest_by_firm[firm] = {'date': date, 'target': t}
                            except:
                                pass
                        
                        targets = [v['target'] for v in latest_by_firm.values()]
                        
                        # current_price already calculated above
                        
                        if targets:
                            avg_target = sum(targets) / len(targets)
                            if current_price > 0:
                                upside = (avg_target - current_price) / current_price * 100
            except Exception as e:
                print(f"Error fetching/saving consensus for {ticker}: {e}")

            summary_item = {
                'ticker': ticker,
                'name': name,
                'industry': final_industry,
                'marketcap': clean_nan(marcap),
                'per': calc_per if calc_per != 0 else snapshot_per,
                'pbr': calc_pbr if calc_pbr != 0 else snapshot_pbr,
                'psr': clean_nan(last_row.get('PSR', 0)),
                'ev_ebitda': clean_nan(last_row.get('EV_EBITDA', 0)),
                'perz': clean_nan(last_row.get('PERZ', 0)),
                'pbrz': clean_nan(last_row.get('PBRZ', 0)),
                'psrz': clean_nan(last_row.get('PSRZ', 0)),
                'ev_ebitdaz': clean_nan(last_row.get('EV_EBITDAZ', 0)),
                'pricez': clean_nan(last_row.get('PRICEZ', 0)),
                'sales_growth': clean_nan(last_row.get('SALES_GROWTH', 0)),
                'op_growth': clean_nan(last_row.get('OP_GROWTH', 0)),
                'np_growth': clean_nan(last_row.get('NP_GROWTH', 0)),
                'target_price': int(avg_target),
                'upside': round(upside, 2),
                'current_price': current_price
            }
            
            # Chart Export
            df_reset = df.reset_index()
            cols_to_save = ['DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 
                            'ADJ_EPS', 'ADJ_BPS', 'ADJ_SPS', 'ADJ_EBITDA', 'ADJ_DEBT_CASH', 'SHARE',
                            'PER', 'PBR', 'PSR', 'EV_EBITDA', 'PRICEZ', 'BASE']
            existing_cols = [c for c in cols_to_save if c in df_reset.columns]
            df_export = df_reset[existing_cols].fillna(0).replace([np.inf, -np.inf], 0)
            chart_data = df_export.to_dict(orient='records')
            

            
            with open(f'public/data/details/{ticker}.json', 'w', encoding='utf-8') as f:
                json.dump(chart_data, f, default=json_serial, separators=(',', ':'))
            
            print("Done")
            return summary_item
            
        except Exception as e:
            print(f"Failed {ticker}: {e}")
            return None

    # Processing Loop (Serial)
    # Threading removed as requested. FDR is fast enough but sensitive to rate limits (Naver).
    print(f"DEBUG: Processing {len(stocks)} stocks.")

    for idx, row in stocks.iterrows():
        res = process_stock(row, broker)
        if res:
            all_tickers_summary.append(res)
        
        # time.sleep removed for performance


    print(f"Stocks done. Total summary items: {len(all_tickers_summary)}")

    # Process ETFs (Keep Serial or Thread? Serial is fine as it's separate loop, but let's thread it too if easy)
    # ETFs are usually fast via FDR? 
    # etfs loop uses etf_data_download which uses fdr.DataReader + LinearReg.
    # fdr is scraping Naver. Naver blocks abusive IPs. 
    # Better run ETFs serially to avoid IP ban from Naver.
    # (Actually data.py etf_data_download uses fdr)
    
    print(f"Processing {len(etfs)} ETFs...")
    for idx, row in etfs.iterrows():
        ticker = row['Symbol']
        name = row['Name']
        # print(f"Processing {ticker} - {name}...", end=" ") # Reduce verbosity for 800+ ETFs
        
        try:
            current_year_length = 250
            df = etf_data_download(ticker=ticker, current_year_length=current_year_length, broker=broker, total='X')
            
            if df is None or df.empty:
                print("Empty Data")
                continue
                
            # Summary Item
            last_row = df.iloc[-1]
            try:
                mcap = float(row.get('Marcap', 0))
            except:
                mcap = 0
                
            summary_item = {
                'ticker': ticker,
                'name': name,
                'industry': 'ETF',
                'marketcap': mcap,
                # ETFs uses PRICEZ only usually
                'pricez': last_row.get('PRICEZ', 0),
                # Others are 0 / null
                'per': 0, 'pbr': 0, 'psr': 0, 'ev_ebitda': 0,
                'perz': 0, 'pbrz': 0, 'psrz': 0, 'ev_ebitdaz': 0,
            }
            all_tickers_summary.append(summary_item)
            
            # Chart Data
            df_reset = df.reset_index()
            # For ETFs, we mainly need price and regression data
            # etf_data_download calculates PRICEZ, BASE, Residuals
            
            cols_to_save = ['DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PRICEZ', 'BASE']
            existing_cols = [c for c in cols_to_save if c in df_reset.columns]
            
            df_reset = df_reset.fillna(0).replace([np.inf, -np.inf], 0)
            
            chart_data = df_reset[existing_cols].to_dict(orient='records')
            
            with open(f'public/data/details/{ticker}.json', 'w', encoding='utf-8') as f:
                json.dump(chart_data, f, default=json_serial, separators=(',', ':'))

            print("Done")
            
        except Exception as e:
            print(f"Fail: {e}")

    # Save Summary List
    with open('public/data/tickers.json', 'w', encoding='utf-8') as f:
        json.dump(all_tickers_summary, f, default=json_serial)
    
    print(f"Completed. Saved {len(all_tickers_summary)} tickers.")

if __name__ == "__main__":
    main()
