#!/usr/bin/env python
"""
Download S&P 500 stocks data for ML training
Using yfinance's built-in S&P 500 index
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
import time
import warnings
warnings.filterwarnings('ignore')

# Top 100 S&P 500 stocks by market cap (manually curated)
# This is enough for meaningful ML training
TOP_100_SP500 = [
    # Mega caps
    'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'UNH',
    'XOM', 'JNJ', 'JPM', 'V', 'PG', 'MA', 'HD', 'CVX', 'MRK', 'ABBV',
    'LLY', 'AVGO', 'PEP', 'KO', 'COST', 'TMO', 'MCD', 'WMT', 'CSCO', 'ACN',
    'ABT', 'BAC', 'CRM', 'DHR', 'NKE', 'PFE', 'DIS', 'ADBE', 'CMCSA', 'VZ',
    'NFLX', 'INTC', 'WFC', 'TXN', 'PM', 'NEE', 'AMD', 'RTX', 'QCOM', 'UPS',
    'HON', 'T', 'BMY', 'SPGI', 'ORCL', 'LOW', 'UNP', 'MS', 'IBM', 'BA',
    'GS', 'CAT', 'AMGN', 'ELV', 'SBUX', 'DE', 'BLK', 'INTU', 'GILD', 'MDT',
    'LMT', 'AXP', 'ISRG', 'CVS', 'SYK', 'ADI', 'PLD', 'MDLZ', 'TJX', 'REGN',
    'ADP', 'C', 'ZTS', 'TMUS', 'VRTX', 'CI', 'MO', 'SO', 'DUK', 'BDX',
    'CL', 'SCHW', 'CME', 'EOG', 'PNC', 'ITW', 'SLB', 'CB', 'MMC', 'NOC',
]

# Add indices/ETFs
INDICES = ['SPY', 'QQQ', 'IWM', 'DIA']

tickers = TOP_100_SP500 + INDICES
print(f"📋 Total tickers: {len(tickers)}")

START_DATE = "2019-01-01"
END_DATE = "2026-02-07"

print(f"\n⬇️  Downloading {len(tickers)} stocks from {START_DATE} to {END_DATE}")
print("   This will take a few minutes...\n")

all_data = []
failed = []
success_count = 0

for i, symbol in enumerate(tickers):
    if (i + 1) % 20 == 0:
        print(f"   Progress: {i+1}/{len(tickers)} ({success_count} successful)")
    
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=START_DATE, end=END_DATE, auto_adjust=False)
        
        if len(df) > 100:  # At least 100 days of data
            df = df.reset_index()
            df['symbol'] = symbol
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low', 
                'Close': 'close',
                'Volume': 'volume'
            })
            df = df[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]
            all_data.append(df)
            success_count += 1
        else:
            failed.append(symbol)
            
        # Rate limiting
        time.sleep(0.05)
        
    except Exception as e:
        failed.append(symbol)
        print(f"   ❌ {symbol}: {e}")

print(f"\n✅ Downloaded {success_count} stocks")
if failed:
    print(f"❌ Failed: {failed}")

if all_data:
    result = pd.concat(all_data, ignore_index=True)
    result['date'] = pd.to_datetime(result['date']).dt.tz_localize(None)
    result = result.sort_values(['date', 'symbol'])
    
    output_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_prices.csv"
    result.to_csv(output_path, index=False)
    
    print(f"\n💾 Saved {len(result)} rows to {output_path}")
    print(f"   Date range: {result['date'].min()} to {result['date'].max()}")
    print(f"   Unique stocks: {result['symbol'].nunique()}")
else:
    print("❌ No data downloaded!")
