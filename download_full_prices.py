#!/usr/bin/env python
"""
Download full historical data for ML training
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Stocks
STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", 
          "META", "TSLA", "AMD", "AVGO", "NFLX", "SPY", "QQQ"]

START_DATE = "2019-01-01"  # Get extra year for 60-day lookback
END_DATE = "2026-02-07"

print("Downloading full historical data...")

all_data = []
for symbol in STOCKS:
    print(f"  {symbol}...", end=" ", flush=True)
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=START_DATE, end=END_DATE, auto_adjust=False)
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
    print(f"{len(df)} rows")

result = pd.concat(all_data, ignore_index=True)
result = result.sort_values(['date', 'symbol'])

output_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/us_prices_full.csv"
result.to_csv(output_path, index=False)

print(f"\nSaved {len(result)} rows to {output_path}")
print(f"Date range: {result['date'].min()} to {result['date'].max()}")
