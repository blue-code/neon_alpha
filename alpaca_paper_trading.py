#!/usr/bin/env python
"""
Alpaca Paper Trading Integration for DoubleEnsemble Strategy

Usage:
1. Set environment variables:
   export ALPACA_API_KEY="your-key"
   export ALPACA_SECRET_KEY="your-secret"
   
2. Run:
   python alpaca_paper_trading.py
"""

import os
import sys
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Check for API keys
API_KEY = os.environ.get('ALPACA_API_KEY')
SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY')

if not API_KEY or not SECRET_KEY:
    print("=" * 60)
    print("🔑 Alpaca API 설정 필요")
    print("=" * 60)
    print("""
Alpaca 페이퍼 트레이딩을 사용하려면:

1. https://alpaca.markets 에서 계정 생성 (무료)
2. Paper Trading API 키 발급
3. 환경변수 설정:
   
   export ALPACA_API_KEY="your-api-key"
   export ALPACA_SECRET_KEY="your-secret-key"

4. 이 스크립트 다시 실행

---
현재 모드: 시뮬레이션 (실제 주문 없음)
""")
    SIMULATION_MODE = True
else:
    SIMULATION_MODE = False
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest

print("=" * 60)
print("DoubleEnsemble Alpaca Paper Trading")
print("=" * 60)

# Load our signals
signals_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/double_ensemble_signals.csv"
signals = pd.read_csv(signals_path)
signals['date'] = pd.to_datetime(signals['date'])

# Get latest signals
latest_date = signals['date'].max()
latest_signals = signals[signals['date'] == latest_date].copy()
latest_signals = latest_signals.sort_values('pred_score', ascending=False)

print(f"\n📅 Latest signal date: {latest_date.date()}")
print(f"📊 Total stocks scored: {len(latest_signals)}")

# Top 10 picks
top_n = 10
top_picks = latest_signals.head(top_n)

print(f"\n🏆 Top {top_n} Picks:")
print("-" * 40)
for i, row in top_picks.iterrows():
    print(f"   {row['symbol']:6s}  score: {row['pred_score']:.6f}")

if SIMULATION_MODE:
    print("\n" + "=" * 60)
    print("📋 시뮬레이션 모드 - 포트폴리오 배분")
    print("=" * 60)
    
    portfolio_value = 100000  # 가상 $100k
    per_stock = portfolio_value / top_n
    
    print(f"\n💰 가상 포트폴리오: ${portfolio_value:,.0f}")
    print(f"📊 종목당 배분: ${per_stock:,.0f} ({100/top_n:.0f}%)")
    print(f"\n🎯 목표 포지션:")
    print("-" * 50)
    
    for i, row in top_picks.iterrows():
        # Simulate with approximate prices
        approx_price = 100  # placeholder
        shares = int(per_stock / approx_price)
        print(f"   {row['symbol']:6s}  ~${per_stock:,.0f}  (~{shares} shares)")
    
    print("\n" + "=" * 60)
    print("✅ 시뮬레이션 완료!")
    print("=" * 60)
    print("""
실제 페이퍼 트레이딩을 하려면:
1. Alpaca 계정 생성 (무료): https://alpaca.markets
2. Paper Trading API 키 발급
3. 환경변수 설정 후 다시 실행
""")

else:
    # Real Alpaca integration
    print("\n🔗 Connecting to Alpaca...")
    
    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    
    # Get account info
    account = trading_client.get_account()
    print(f"\n💰 Account Status:")
    print(f"   Equity:        ${float(account.equity):,.2f}")
    print(f"   Buying Power:  ${float(account.buying_power):,.2f}")
    print(f"   Cash:          ${float(account.cash):,.2f}")
    
    # Get current positions
    positions = trading_client.get_all_positions()
    current_holdings = {p.symbol: float(p.qty) for p in positions}
    
    print(f"\n📊 Current Positions: {len(positions)}")
    for p in positions:
        print(f"   {p.symbol}: {p.qty} shares @ ${float(p.avg_entry_price):.2f}")
    
    # Calculate target positions
    equity = float(account.equity)
    per_stock = equity / top_n
    target_symbols = set(top_picks['symbol'].tolist())
    
    print(f"\n🎯 Target Allocation:")
    print(f"   ${per_stock:,.2f} per stock ({top_n} stocks)")
    
    # Get current prices
    symbols_to_trade = list(target_symbols | set(current_holdings.keys()))
    
    try:
        quotes = data_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbols_to_trade))
        prices = {sym: float(q.ask_price) for sym, q in quotes.items()}
    except Exception as e:
        print(f"   Warning: Could not get live quotes: {e}")
        prices = {}
    
    # Generate orders
    print(f"\n📝 Order Plan:")
    print("-" * 60)
    
    orders = []
    
    # Close positions not in target
    for symbol, qty in current_holdings.items():
        if symbol not in target_symbols:
            orders.append({
                'symbol': symbol,
                'side': 'sell',
                'qty': int(qty),
                'reason': 'exit'
            })
    
    # Open/adjust positions in target
    for symbol in target_symbols:
        current_qty = current_holdings.get(symbol, 0)
        
        if symbol in prices:
            price = prices[symbol]
            target_qty = int(per_stock / price)
        else:
            target_qty = 0
            
        diff = target_qty - current_qty
        
        if diff > 0:
            orders.append({
                'symbol': symbol,
                'side': 'buy',
                'qty': int(diff),
                'reason': 'enter/increase'
            })
        elif diff < -1:
            orders.append({
                'symbol': symbol,
                'side': 'sell',
                'qty': int(-diff),
                'reason': 'decrease'
            })
    
    for order in orders:
        action = "🟢 BUY" if order['side'] == 'buy' else "🔴 SELL"
        print(f"   {action} {order['qty']:4d} {order['symbol']:6s} ({order['reason']})")
    
    if not orders:
        print("   No orders needed - portfolio is balanced!")
    
    # Ask for confirmation
    print("\n" + "=" * 60)
    confirm = input("Execute orders? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        print("\n🚀 Executing orders...")
        for order in orders:
            try:
                side = OrderSide.BUY if order['side'] == 'buy' else OrderSide.SELL
                req = MarketOrderRequest(
                    symbol=order['symbol'],
                    qty=order['qty'],
                    side=side,
                    time_in_force=TimeInForce.DAY
                )
                result = trading_client.submit_order(req)
                print(f"   ✅ {order['side'].upper()} {order['qty']} {order['symbol']}: {result.status}")
            except Exception as e:
                print(f"   ❌ {order['symbol']}: {e}")
        
        print("\n✅ Orders submitted!")
    else:
        print("\n❌ Cancelled - no orders executed")

print("\n" + "=" * 60)
