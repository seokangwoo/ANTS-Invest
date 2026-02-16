import mojito
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv('KIS_APP_KEY')
secret = os.getenv('KIS_APP_SECRET')
acc_no = os.getenv('KIS_ACCOUNT')

# Mock credentials if env not set, just to inspect class
if not key:
    key = "test"
    secret = "test"
    acc_no = "test"

broker = mojito.KoreaInvestment(
    api_key=key,
    api_secret=secret,
    acc_no=acc_no,
    mock=True
)

print(dir(broker))
