from korea_investment_stock import KoreaInvestment
import os
from dotenv import load_dotenv
import json

load_dotenv()

key = os.getenv('KIS_APP_KEY')
secret = os.getenv('KIS_APP_SECRET')
acc_no = os.getenv('KIS_ACCOUNT')

if not key or not secret:
    print("No credentials found. Cannot test real API.")
    # Assuming the user has credentials in .env as per previous context
    # If not, I can't really test.
    exit(1)

broker = KoreaInvestment(
    api_key=key,
    api_secret=secret,
    acc_no=acc_no,
    mock=False # Must be False for search_stock_info
)

try:
    # Use the private method access or if there is a public one?
    # The code showed __fetch_search_stock_info.
    # Is there a public wrapper?
    # I did not see it in the grep.
    # I will look at the file again or just try to access it via name mangling.
    print("Calling search_stock_info...")
    # It might be exposed as 'fetch_stock_info' or similar?
    # Let's inspect dir(broker)
    print(dir(broker))
    
    # Trying the name found in grep: fetch_search_stock_info (if public? no, double underscore)
    # But usually there is a public method calling it.
    
    # Let's try to call it via private name mangling if needed: _KoreaInvestment__fetch_search_stock_info
    res = broker._KoreaInvestment__fetch_search_stock_info('005930', 'KR')
    print(json.dumps(res, indent=2, ensure_ascii=False))

except Exception as e:
    print(f"Error: {e}")
