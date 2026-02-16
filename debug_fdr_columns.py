
import FinanceDataReader as fdr
import pandas as pd

try:
    print("Fetching KOSPI...")
    df = fdr.StockListing('KOSPI')
    print("Columns:", df.columns.tolist())
    if not df.empty:
        print("First row:", df.iloc[0].to_dict())
except Exception as e:
    print(f"Error: {e}")
