
import os
import sys
from dotenv import load_dotenv
import json

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ANTS.kis_api import KisApi

def main():
    print("--- DEBUG CI START ---")
    load_dotenv()
    
    key = os.getenv('KIS_APP_KEY')
    secret = os.getenv('KIS_APP_SECRET')
    acc_no = os.getenv('KIS_ACCOUNT')
    
    if not key:
        print("Keys missing in env.")
        return

    broker = KisApi(key, secret, acc_no, mock=False)
    if not broker.access_token:
        print("Auth Failed")
        return
        
    ticker = "005930"
    print(f"Fetching Price Detail for {ticker}...")
    res = broker.fetch_price_detail(ticker)
    print("Raw Response Keys:", res.keys())
    if 'output' in res:
        print("Output Keys:", res['output'].keys())
        print("hts_avls:", res['output'].get('hts_avls'))
        print("per:", res['output'].get('per'))
        print("pbr:", res['output'].get('pbr'))
    else:
        print("No output in response:", res)
        
    print(f"\nFetching Financial Ratio for {ticker}...")
    res = broker.fetch_financial_ratio(ticker)
    if 'output' in res:
        print("Output Len:", len(res['output']))
        if len(res['output']) > 0:
            print("First Row:", res['output'][0])
    else:
        print("No output in financial ratio:", res)

    print("--- DEBUG CI END ---")

if __name__ == "__main__":
    main()
