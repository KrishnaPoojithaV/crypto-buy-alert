# !pip install ccxt ta pandas twilio

import pandas as pd
import ccxt
from ta.trend import MACD, SMAIndicator
from twilio.rest import Client
from datetime import datetime
import pytz
import os
import warnings
warnings.filterwarnings('ignore')


# Parameters
symbol = 'BNB/USDT'
timeframe = '3m'  # Options: '15m', '1h', '4h', etc.
limit = 100  # Number of candles to fetch
zero_threshold = 0.002  # defines "near zero" region

# Twilio credentials (use environment variables or secrets)
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")   # your Twilio phone number, e.g. "+1234567890"
TWILIO_TO = os.getenv("TWILIO_TO")       # your verified personal number, e.g. "+1987654321"

# exchange = ccxt.bybit({'enableRateLimit': True}) - working for Global regions (binance is blocked for US regions)

# exchange = ccxt.binance({
#     'enableRateLimit': True,
# })

# Initialize Binance
exchange = ccxt.binanceus({'enableRateLimit': True})

# Function to fetch historical data
def fetch_data():
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Function to make call via Twilio
def make_call_alert(message: str):
    """Trigger a phone call that speaks the given message."""
    if not all([TWILIO_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, TWILIO_TO]):
        print("Twilio credentials missing.")
        return

    try:
        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        call = client.calls.create(
            twiml=f"<Response><Say>{message}</Say></Response>",
            to=TWILIO_TO,
            from_=TWILIO_FROM
        )
        print(f"📞 Call initiated! SID: {call.sid}")
    except Exception as e:
        print(f"❌ Twilio call failed: {e}")

# Function to calculate indicators and check alert condition
def check_buy_alert(df):
    df['ma7'] = SMAIndicator(df['close'], window=7).sma_indicator()
    df['ma25'] = SMAIndicator(df['close'], window=25).sma_indicator()
    df['ma99'] = SMAIndicator(df['close'], window=99).sma_indicator()

    macd = MACD(df['close'])
    df['DIF'] = macd.macd()         # MACD line
    df['DEA'] = macd.macd_signal()  # Signal line

    # Check for NaN values in the last two rows
    if df[['ma7', 'ma25', 'ma99', 'DIF', 'DEA']].iloc[-2:].isnull().any().any():
        return False

    prev = df.iloc[-2]
    prev_dif, prev_dea = prev['DIF'], prev['DEA']

    curr = df.iloc[-1]
    curr_dif, curr_dea = curr['DIF'], curr['DEA']

    # Convert UTC timestamp to IST
    utc_time = curr['timestamp']
    if isinstance(utc_time, str):
        utc_time = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))  # handle ISO string
    utc_time = utc_time.replace(tzinfo=pytz.utc)
    ist_time = utc_time.astimezone(pytz.timezone('Asia/Kolkata'))

    print(f"Timestamp (UTC): {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Timestamp (IST): {ist_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Current Price: {curr['close']:.2f}")
    print(f"MA7: {curr['ma7']:.2f}, MA25: {curr['ma25']:.2f}, MA99: {curr['ma99']:.2f}")
    print(f"DIF: {curr_dif:.2f}, DEA: {curr_dea:.2f}")
    
    # Condition 1: DIF crosses above DEA
    crossover = prev_dif < prev_dea and curr_dif > curr_dea
    
    # Condition 2: Both are near or below the zero line (reversal signal)
    near_zero = curr_dif < zero_threshold and curr_dea < zero_threshold
    
    return crossover and near_zero

df = fetch_data()
if check_buy_alert(df):
    print("🔔 Buy Alert Triggered!")
    msg = f" BUY ALERT for {symbol} at {df['timestamp'].iloc[-1]}"
    print(msg)
    make_call_alert(f"Buy alert triggered for {symbol} at {df['timestamp'].iloc[-1]}")
else:
    print("No Buy Signal.")
