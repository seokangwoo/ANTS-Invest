import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import time

# Configuration
OUTPUT_DIR = "public/data/us/Details"
CONSENSUS_DIR = "public/data/us/Consensus"
TICKERS_FILE = "public/data/us/tickers.json"

# Fetch S&P 500 List
try:
    print("Fetching S&P 500 list from FDR...")
    sp500 = fdr.StockListing('S&P500')
    STOCKS = sp500['Symbol'].tolist() 
    print(f"Loaded {len(STOCKS)} S&P 500 stocks via FDR.")
except Exception as e:
    print(f"Error fetching S&P 500 via FDR: {e}")
    # Final Fallback (Hardcoded min list just to not crash completely if FDR fails, or empty?)
    STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "WMT", "JPM"]
    print("Used small hardcoded fallback.") 

# ETFs (Top Market Cap 200)
try:
    print("Fetching US ETF list...")
    etf_df = fdr.StockListing('ETF/US')
    # Use top 300 candidates from fdr (roughly sorted by popularity) and refine by Market Cap
    candidates = etf_df['Symbol'].tolist()[:300]
    
    # 1. Fetch Market Cap for Candidates
    print(f"Fetching Market Cap for {len(candidates)} candidates to filter Top 200...")
    etf_caps = []
    
    # Batch processing with yfinance could be faster?
    # yf.Tickers(" ".join(candidates)) might be too long URL.
    # Split into chunks of 50
    chunks = [candidates[i:i + 50] for i in range(0, len(candidates), 50)]
    
    for chunk in chunks:
        try:
            tickers_obj = yf.Tickers(" ".join(chunk))
            for sym, ticker_obj in tickers_obj.tickers.items():
                try:
                    # fast_info is faster than info
                    mcap = ticker_obj.fast_info.market_cap
                    if mcap and mcap > 0:
                        etf_caps.append({'symbol': sym, 'mcap': mcap})
                except:
                    pass
        except Exception as e:
            print(f"Chunk error: {e}")
            
    # 2. Sort by MarCap Desc
    etf_caps.sort(key=lambda x: x['mcap'], reverse=True)
    
    # 3. Take Top 200
    top_200 = etf_caps[:200]
    ETFS = [x['symbol'] for x in top_200]

    print(f"Selected Top {len(ETFS)} ETFs by Market Cap.")
except Exception as e:
    print(f"Error fetching US ETFs: {e}")
    # Fallback
    ETFS = [
        "SPY", "QQQ", "SOXL", "TQQQ", "IWM", "DIA", "VOO", "SCHD", "JEPI", "GLD"
    ]

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CONSENSUS_DIR, exist_ok=True)
os.makedirs("public/data/us", exist_ok=True)

def safe_float(val):
    try:
        if val is None: return 0.0
        return float(val)
    except:
        return 0.0

def process_us_stock(ticker_symbol, is_etf=False):
    # ... existing code ...
    pass 
    # (Actually I shouldn't replace entire function just for header. 
    # I will target header area and the debug print area separately or together if close).

# I will use multi-replace or careful single replace.
# The `process_us_stock` logic is far below.
# I will replace the imports and lists first.

# Wait, `replace_file_content` targets lines.
# I will Target the TOP of the file to add imports and list.
# Then Target the DEBUG PRINTS (Lines 262-265, 273-274, 292-293) to remove them.

    print(f"Processing {ticker_symbol} (ETF={is_etf})...")
    ticker = yf.Ticker(ticker_symbol)
    
    # 1. Price History
    try:
        hist = ticker.history(period="max")
        if hist.empty:
            print(f"  No price data for {ticker_symbol}")
            return None
        hist.index = hist.index.tz_localize(None) # Remove timezone
        hist.reset_index(inplace=True)
        hist['Date'] = hist['Date'].dt.strftime('%Y-%m-%d')
        hist = hist.set_index('Date')
    except Exception as e:
        print(f"  Error fetching price: {e}")
        return None

    # Enable Financials only for Stocks
    annual_data = pd.DataFrame() # Default empty
    
    if not is_etf:
        try:
            financials = ticker.financials.T
            balance = ticker.balance_sheet.T
            cashflow = ticker.cashflow.T
            
            annual_data = pd.DataFrame(index=financials.index)
            
            # EPS
            if 'Diluted EPS' in financials.columns: annual_data['EPS'] = financials['Diluted EPS']
            elif 'Basic EPS' in financials.columns: annual_data['EPS'] = financials['Basic EPS']
            else: annual_data['EPS'] = np.nan
            
            # Revenue (for PSR)
            if 'Total Revenue' in financials.columns: annual_data['REV'] = financials['Total Revenue']
            else: annual_data['REV'] = np.nan

            # EBITDA
            if 'EBITDA' in financials.columns: annual_data['EBITDA'] = financials['EBITDA']
            else: annual_data['EBITDA'] = np.nan
            
            # Operating Income (for POR)
            if 'Operating Income' in financials.columns: annual_data['OP_INC'] = financials['Operating Income']
            else: annual_data['OP_INC'] = np.nan
            
            # Equity (for PBR)
            balance = balance.reindex(annual_data.index) # Align
            if 'Stockholders Equity' in balance.columns: annual_data['EQUITY'] = balance['Stockholders Equity']
            elif 'Total Equity Gross Minority Interest' in balance.columns: annual_data['EQUITY'] = balance['Total Equity Gross Minority Interest']
            else: annual_data['EQUITY'] = np.nan
            
            # Debt & Cash (for EV)
            if 'Total Debt' in balance.columns: annual_data['DEBT'] = balance['Total Debt']
            else: annual_data['DEBT'] = 0
            
            if 'Cash And Cash Equivalents' in balance.columns: annual_data['CASH'] = balance['Cash And Cash Equivalents']
            else: annual_data['CASH'] = 0
            
            # Shares
            if 'Basic Average Shares' in financials.columns: annual_data['SHARES'] = financials['Basic Average Shares']
            elif 'Ordinary Shares Number' in balance.columns: annual_data['SHARES'] = balance['Ordinary Shares Number']
            else: annual_data['SHARES'] = 1 
            
            # Operating Cash Flow (for PCR)
            cashflow = cashflow.reindex(annual_data.index)
            if 'Operating Cash Flow' in cashflow.columns: annual_data['OCF'] = cashflow['Operating Cash Flow']
            else: annual_data['OCF'] = np.nan
            
            # Prepare for Merge
            annual_data.sort_index(inplace=True)
            annual_data.index = annual_data.index.tz_localize(None).strftime('%Y-%m-%d')
            
            # --- Forecast Data Integration (New) ---
            try:
                estimates = ticker.earnings_estimate
                if estimates is not None and not estimates.empty:
                    # '0y' = Current Fiscal Year (e.g. 2026 if last actual was 2025)
                    # '+1y' = Next Fiscal Year
                    
                    last_date_str = annual_data.index.max()
                    last_date = pd.to_datetime(last_date_str)
                    
                    # Determine next fiscal year end
                    # Simple logic: Add 1 year to last actual date
                    next_year_date = last_date + pd.DateOffset(years=1)
                    next_next_year_date = last_date + pd.DateOffset(years=2)
                    
                    next_year_str = next_year_date.strftime('%Y-%m-%d')
                    next_next_year_str = next_next_year_date.strftime('%Y-%m-%d')
                    
                    # Extract EPS
                    eps_0y = safe_float(estimates.loc['0y', 'avg']) if '0y' in estimates.index else 0
                    eps_1y = safe_float(estimates.loc['+1y', 'avg']) if '+1y' in estimates.index else 0
                    
                    # Create new rows (if EPS is valid)
                    if eps_0y != 0:
                        new_row_0y = pd.Series(index=annual_data.columns, dtype='float64')
                        new_row_0y['EPS'] = eps_0y
                        # Carry forward other metrics (Subject to improvement, but keeps EV/EBITDA somewhat stable if we assume flat)
                        # Actually, keeping others NaN might be safer or carry forward?
                        # Z-Score needs EPS. Let's carry forward others to allow PBR/PSR calculation if price exists?
                        # Or just leave NaN and let logic handle.
                        # build_data logic uses interpolation. If we add a row with only EPS, others will be NaN.
                        # Then interpolate/ffill will fill them if we are careful.
                        # Let's fill with last known values for stability.
                        last_row = annual_data.iloc[-1]
                        new_row_0y['REV'] = last_row.get('REV')
                        new_row_0y['EBITDA'] = last_row.get('EBITDA')
                        new_row_0y['OP_INC'] = last_row.get('OP_INC')
                        new_row_0y['EQUITY'] = last_row.get('EQUITY')
                        new_row_0y['DEBT'] = last_row.get('DEBT')
                        new_row_0y['CASH'] = last_row.get('CASH')
                        new_row_0y['SHARES'] = last_row.get('SHARES')
                        
                        annual_data.loc[next_year_str] = new_row_0y
                        
                    if eps_1y != 0:
                        new_row_1y = pd.Series(index=annual_data.columns, dtype='float64')
                        new_row_1y['EPS'] = eps_1y
                        # Carry forward
                        last_row = annual_data.iloc[-1] # This is now the 0y row if added
                        new_row_1y['REV'] = last_row.get('REV')
                        new_row_1y['EBITDA'] = last_row.get('EBITDA')
                        new_row_1y['OP_INC'] = last_row.get('OP_INC')
                        new_row_1y['EQUITY'] = last_row.get('EQUITY')
                        new_row_1y['DEBT'] = last_row.get('DEBT')
                        new_row_1y['CASH'] = last_row.get('CASH')
                        new_row_1y['SHARES'] = last_row.get('SHARES')

                        annual_data.loc[next_next_year_str] = new_row_1y
                        
                    print(f"  Added Forecasts: {next_year_str} (EPS {eps_0y}), {next_next_year_str} (EPS {eps_1y})")
                    
            except Exception as e:
                print(f"  Error adding forecasts: {e}")

        except Exception as e:
            print(f"  Error fetching financials: {e}")
            annual_data = pd.DataFrame()

    # 3. Merge Price and Annual Data
    merged = hist.copy()
    merged['DATE'] = merged.index
    
    # Initialize metric columns
    metric_cols = ['EPS', 'REV', 'EBITDA', 'OP_INC', 'EQUITY', 'DEBT', 'CASH', 'SHARES', 'OCF']
    for col in metric_cols:
        merged[col] = np.nan
        
    if not annual_data.empty:
        merged_idx = pd.to_datetime(merged.index)
        # Re-convert annual index to datetime for logic
        reindexed_annual = annual_data.copy()
        reindexed_annual.index = pd.to_datetime(reindexed_annual.index)
        
        # Smooth Interpolation logic (Linear between quarters/years)
        # 1. Create a union index of Price Dates and Financial Dates
        annual_idx = reindexed_annual.index
        combined_idx = merged_idx.union(annual_idx).sort_values()
        
        # 2. Reindex annual to this combined index
        full_annual = reindexed_annual.reindex(combined_idx)
        
        # 3. Interpolate
        # 'time' method respects the time distance
        full_annual = full_annual.interpolate(method='time')
        
        # 4. Forward fill the remaining (e.g. latest date to current date)
        # Interpolate only fills between known points. Trailing edge needs ffill.
        full_annual = full_annual.ffill()
        
        # 5. Extract only rows matching Price Dates
        aligned_annual = full_annual.reindex(merged_idx).ffill() # Extra ffill just in case
        
        for col in metric_cols:
            if col in aligned_annual:
                merged[col] = aligned_annual[col].values

    # 4. Calculate Per Share Ratios & EV
    merged = merged.fillna(0)
    
    close = merged['Close']
    shares = merged['SHARES'].replace(0, 1)
    
    merged['PER'] = close / (merged['EPS'].replace(0, np.nan))
    merged['PBR'] = close / ((merged['EQUITY']/shares).replace(0, np.nan))
    merged['PSR'] = close / ((merged['REV']/shares).replace(0, np.nan))
    
    market_cap = close * shares
    ev = market_cap + merged['DEBT'] - merged['CASH']
    merged['EV_EBITDA'] = ev / (merged['EBITDA'].replace(0, np.nan))
    
    merged['PCR'] = close / ((merged['OCF']/shares).replace(0, np.nan))
    merged['POR'] = close / ((merged['OP_INC']/shares).replace(0, np.nan))

    # Dividend Yield (Price Z-Score Base logic remains)
    try:
        divs = ticker.dividends
        if not divs.empty:
            divs.index = divs.index.tz_localize(None)
            div_series = pd.Series(0.0, index=pd.to_datetime(merged.index))
            common_idx = divs.index.intersection(div_series.index)
            div_series.loc[common_idx] = divs.loc[common_idx]
            
            rolling_div = div_series.rolling('365D').sum()
            merged['YIELD'] = (rolling_div / close) * 100 
        else:
            merged['YIELD'] = 0.0
    except:
        merged['YIELD'] = 0.0

    # 5. Base Regression
    n = len(merged)
    if n > 0:
        x = np.arange(n)
        y = merged['Close'].values
        slope, intercept = np.polyfit(x, y, 1)
        merged['BASE'] = slope * x + intercept
    else:
        merged['BASE'] = 0
        
    merged['ADJ_EPS'] = merged['EPS']
    merged['ADJ_BPS'] = merged['EQUITY'] / shares
    merged['ADJ_SPS'] = merged['REV'] / shares
    merged['ADJ_EBITDA'] = merged['EBITDA']
    merged['ADJ_DEBT_CASH'] = merged['DEBT'] - merged['CASH']
    merged['SHARE'] = shares
    merged['ADJ_CPS'] = merged['OCF'] / shares
    merged['ADJ_OPS'] = merged['OP_INC'] / shares
    
    merged['CLOSE'] = merged['Close']
    merged['OPEN'] = merged['Open']
    merged['HIGH'] = merged['High']
    merged['LOW'] = merged['Low']
    
    merged = merged.replace([np.inf, -np.inf], 0).fillna(0)
    
    export_cols = [
        'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'BASE',
        'ADJ_EPS', 'ADJ_BPS', 'ADJ_SPS', 'ADJ_EBITDA', 'ADJ_DEBT_CASH', 'SHARE',
        'ADJ_CPS', 'ADJ_OPS', 'YIELD',
        'PER', 'PBR', 'PSR', 'EV_EBITDA', 'PCR', 'POR'
    ]
    
    final_cols = [c for c in export_cols if c in merged.columns]
    output_data = merged[final_cols].to_dict(orient='records')
    
    for row in output_data:
        if isinstance(row['DATE'], pd.Timestamp):
            row['DATE'] = row['DATE'].strftime('%Y-%m-%d')

    with open(f"{OUTPUT_DIR}/{ticker_symbol}.json", "w") as f:
        json.dump(output_data, f, default=str)
        
    # Consensus
    try:
        upgrades = ticker.upgrades_downgrades
        consensus_list = []
        latest_by_firm = {}
        
        if upgrades is not None and not upgrades.empty:
            # Sort by date descending
            upgrades = upgrades.sort_index(ascending=False)
            
            # Limit to recent 2 years for list display? Or calculate avg from all available?
            # User said "latest value per firm".
            # Let's iterate all (or reasonable history)
            
            upgrades_reset = upgrades.reset_index() # GradeDate becomes column
            
            for _, r in upgrades_reset.iterrows():
                # Extract Target
                tgt = 0
                try:
                    # yfinance often puts target in 'currentPriceTarget' if available
                    if 'currentPriceTarget' in r and pd.notnull(r['currentPriceTarget']):
                        tgt = float(r['currentPriceTarget'])
                    # Sometimes in 'ToGrade' if it's mixed? No.
                except:
                    tgt = 0

                firm = r.get('Firm', '')
                date_val = r['GradeDate']
                date_str = date_val.strftime('%Y-%m-%d') if pd.notnull(date_val) else ""
                
                item = {
                    "date": date_str,
                    "firm": firm,
                    "action": r.get('Action', ''),
                    "grade_from": r.get('FromGrade', ''),
                    "grade_to": r.get('ToGrade', ''),
                    "target": tgt
                }
                consensus_list.append(item)
                
                # Logic for Avg Target (Latest per Firm)
                if firm and tgt > 0:
                     if firm not in latest_by_firm:
                         latest_by_firm[firm] = {'date': date_val, 'target': tgt}
                     # Since we iterate desc, first seen is latest. No need to check date > current.
                     
    except Exception as e:
        print(f"  Error fetching upgrades: {e}")
        consensus_list = []
        latest_by_firm = {}
        
    with open(f"{CONSENSUS_DIR}/{ticker_symbol}.json", "w") as f:
        json.dump(consensus_list, f, default=str)

    # Name Fetching
    try:
        # Optimizing: only fetch info if needed. But we need name.
        # info object is cached?
        short_name = ticker.info.get('shortName', ticker_symbol)
        # Sometimes shortName is None
        if not short_name: short_name = ticker_symbol
    except:
        short_name = ticker_symbol

    # Price Z-Score (Regression)
    # BASE already calculated (Line 187)
    merged['Residuals'] = merged['Close'] - merged['BASE']
    residuals_std = merged['Residuals'].std()
    
    if residuals_std != 0:
        merged['PRICEZ'] = merged['Residuals'] / residuals_std
    else:
        merged['PRICEZ'] = 0.0

    # Calculate Z-Scores for Summary
    def calculate_z(series):
        # Filter valid
        valid = series[series != 0]
        if valid.empty: return 0.0
        mean = valid.mean()
        std = valid.std()
        if std == 0: return 0.0
        current = series.iloc[-1]
        return (current - mean) / std

    per_z = calculate_z(merged['PER'])
    pbr_z = calculate_z(merged['PBR'])
    psr_z = calculate_z(merged['PSR'])
    ev_ebitda_z = calculate_z(merged['EV_EBITDA'])
    price_z = merged['PRICEZ'].iloc[-1] if not merged.empty else 0.0
    
    mcap_val = safe_float(merged['CLOSE'].iloc[-1] * shares.iloc[-1])
    current_price_val = safe_float(merged['CLOSE'].iloc[-1])

    # Calculate Consensus Summary
    try:
        targets = [v['target'] for v in latest_by_firm.values()]
        if targets:
            avg_target = sum(targets) / len(targets)
            if current_price_val > 0:
                upside_val = (avg_target - current_price_val) / current_price_val * 100
            else:
                upside_val = 0
        else:
            avg_target = 0
            upside_val = 0
    except:
        avg_target = 0
        upside_val = 0

    # Return Summary
    return {
        "ticker": ticker_symbol,
        "name": short_name, # Real Name
        "industry": "ETF" if is_etf else "US Stock",
        "marketcap": mcap_val,
        # Last values
        "per": safe_float(merged['PER'].iloc[-1]),
        "pbr": safe_float(merged['PBR'].iloc[-1]),
        "psr": safe_float(merged['PSR'].iloc[-1]),
        "ev_ebitda": safe_float(merged['EV_EBITDA'].iloc[-1]),
        "pcr": safe_float(merged['PCR'].iloc[-1]),
        "por": safe_float(merged['POR'].iloc[-1]),
        "yield": safe_float(merged['YIELD'].iloc[-1]),
        # Z-Scores
        "perz": safe_float(per_z),
        "pbrz": safe_float(pbr_z),
        "psrz": safe_float(psr_z),
        "ev_ebitdaz": safe_float(ev_ebitda_z), # keys match page.tsx
        "pricez": safe_float(price_z),
        # Consensus
        "target_price": int(avg_target),
        "upside": round(upside_val, 2),
        "current_price": current_price_val 
    }

summary_list = []

# Process Stocks
# STOCKS = STOCKS[:20]  <-- Already removed/commented in previous steps?
# Let's check headers. The limit was in the headers. I will check headers next.
# But here we iterate STOCKS.
for t in STOCKS:
    start = time.time()
    try:
        info = process_us_stock(t, is_etf=False)
        if info: summary_list.append(info)
        print(f"Done {t}: {time.time()-start:.2f}s")
    except Exception as e:
        print(f"Error {t}: {e}")
        import traceback
        traceback.print_exc()

# Process ETFs
for t in ETFS:
    start = time.time()
    try:
        info = process_us_stock(t, is_etf=True)
        if info: summary_list.append(info)
        print(f"Done {t}: {time.time()-start:.2f}s")
    except Exception as e:
        print(f"Error {t}: {e}")
        import traceback
        traceback.print_exc()

# Calculate Z-Scores for Summary (Relative to history? Or Cross-sectional?)
# Existing KR site uses "Z-Score from History" (computed in Chart?).
# Ah, summary table Z-Score columns (perz, pbrz...) are "Current vs Self History"?
# `build_data.py` calculates Z-Score on "Last Row" vs "Historical Stats".
# I didn't calculate Z in `process_us_stock` for summary.
# I should add it.
# Simple (Last - Mean) / Std for whole history (or 5 years).
# I'll update `process_us_stock` logic or do it post-process?
# Inside `process_us_stock` is easier.
# (Code simplified here for brevity, I assumes 0 for now or update later)

with open(TICKERS_FILE, "w") as f:
    json.dump(summary_list, f, indent=2)

print("US Data Build Complete.")
