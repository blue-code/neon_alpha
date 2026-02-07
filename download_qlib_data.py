#!/usr/bin/env python
"""
Download US stock data and convert to Qlib format
Simpler approach: just download our target stocks directly
"""

import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
import struct
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Our target stocks
STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", 
          "META", "TSLA", "AMD", "AVGO", "NFLX", "SPY", "QQQ"]

# Date range
START_DATE = "2020-01-01"
END_DATE = "2026-02-07"

# Output directory
QLIB_DATA_DIR = Path(os.path.expanduser("~/.qlib/qlib_data/us_data_custom"))

print("=" * 60)
print("Downloading US Stock Data for Qlib")
print("=" * 60)

# Create directories
features_dir = QLIB_DATA_DIR / "features"
calendars_dir = QLIB_DATA_DIR / "calendars"
instruments_dir = QLIB_DATA_DIR / "instruments"

for d in [features_dir, calendars_dir, instruments_dir]:
    d.mkdir(parents=True, exist_ok=True)

print(f"\n📁 Output: {QLIB_DATA_DIR}")
print(f"📅 Period: {START_DATE} to {END_DATE}")
print(f"📊 Stocks: {len(STOCKS)}")

# Download data
print("\n⬇️  Downloading from Yahoo Finance...")

all_data = {}
all_dates = set()

for symbol in STOCKS:
    print(f"   {symbol}...", end=" ", flush=True)
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=START_DATE, end=END_DATE, auto_adjust=False)
        
        if len(df) > 0:
            all_data[symbol] = df
            all_dates.update(df.index.strftime("%Y-%m-%d").tolist())
            print(f"✓ {len(df)} rows")
        else:
            print("❌ No data")
    except Exception as e:
        print(f"❌ {e}")

print(f"\n📈 Downloaded {len(all_data)} stocks")

# Create calendar file
print("\n📅 Creating calendar...")
calendar_dates = sorted(list(all_dates))
calendar_path = calendars_dir / "day.txt"
with open(calendar_path, 'w') as f:
    f.write('\n'.join(calendar_dates))
print(f"   {len(calendar_dates)} trading days")

# Create instruments file
print("\n📋 Creating instruments list...")
instruments_path = instruments_dir / "all.txt"
with open(instruments_path, 'w') as f:
    for symbol in all_data.keys():
        # Get first and last date for each symbol
        df = all_data[symbol]
        first_date = df.index.min().strftime("%Y-%m-%d")
        last_date = df.index.max().strftime("%Y-%m-%d")
        f.write(f"{symbol}\t{first_date}\t{last_date}\n")

# Convert to Qlib bin format
print("\n🔄 Converting to Qlib format...")

def float_to_bin(value):
    """Convert float to Qlib binary format"""
    if pd.isna(value):
        return struct.pack('<f', np.nan)
    return struct.pack('<f', float(value))

for symbol, df in all_data.items():
    print(f"   {symbol}...", end=" ", flush=True)
    
    symbol_dir = features_dir / symbol.lower()
    symbol_dir.mkdir(exist_ok=True)
    
    # Sort by date
    df = df.sort_index()
    
    # Fields to save (lowercase for Qlib)
    fields = {
        'open': df['Open'],
        'high': df['High'],
        'low': df['Low'],
        'close': df['Close'],
        'volume': df['Volume'],
        'factor': df['Adj Close'] / df['Close'],  # adjustment factor
    }
    
    for field_name, values in fields.items():
        bin_path = symbol_dir / f"{field_name}.day.bin"
        with open(bin_path, 'wb') as f:
            for val in values:
                f.write(float_to_bin(val))
    
    print("✓")

print("\n" + "=" * 60)
print("✅ Qlib data created!")
print("=" * 60)
print(f"\nTo use this data, initialize Qlib with:")
print(f'  qlib.init(provider_uri="{QLIB_DATA_DIR}", region=REG_US)')
