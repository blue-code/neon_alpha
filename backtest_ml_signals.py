#!/usr/bin/env python
"""
Backtest ML signals with Backtrader
Compare ML-based strategy with momentum strategy
"""

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Load data
print("=" * 60)
print("Backtesting ML Signals")
print("=" * 60)

prices = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/us_prices_full.csv")
prices['date'] = pd.to_datetime(prices['date'], utc=True).dt.tz_localize(None)

signals = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/ml_signals.csv")
signals['date'] = pd.to_datetime(signals['date'], utc=True).dt.tz_localize(None)

print(f"Prices: {len(prices)} rows")
print(f"Signals: {len(signals)} rows")
print(f"Signal period: {signals['date'].min()} to {signals['date'].max()}")

# Get stocks in both datasets (exclude ETFs for now)
stocks = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AMD', 'AVGO', 'NFLX']

class MLSignalStrategy(bt.Strategy):
    """Strategy using ML signals"""
    
    params = dict(
        rebalance_days=5,  # rebalance every 5 days (same as signal horizon)
        top_n=3,
    )
    
    def __init__(self):
        self.order = None
        self.day_count = 0
        
    def next(self):
        # Only rebalance every N days
        self.day_count += 1
        if self.day_count % self.p.rebalance_days != 0:
            return
            
        # Get current date
        current_date = self.datas[0].datetime.date(0)
        
        # Get ML signals for this date
        date_signals = signals[signals['date'].dt.date == current_date]
        
        if len(date_signals) == 0:
            return
        
        # Get top N stocks by ML score
        top_stocks = date_signals.nlargest(self.p.top_n, 'pred_score')['symbol'].tolist()
        
        # Calculate target positions
        target_weight = 1.0 / self.p.top_n
        
        # Close positions not in top_stocks
        for data in self.datas:
            if data._name not in top_stocks and self.getposition(data).size > 0:
                self.close(data)
        
        # Open positions in top_stocks
        for data in self.datas:
            if data._name in top_stocks:
                target_value = self.broker.getvalue() * target_weight
                current_value = self.getposition(data).size * data.close[0]
                diff = target_value - current_value
                
                if abs(diff) > self.broker.getvalue() * 0.05:  # Only trade if diff > 5%
                    if diff > 0:
                        size = int(diff / data.close[0])
                        if size > 0:
                            self.buy(data, size=size)
                    else:
                        size = int(-diff / data.close[0])
                        if size > 0:
                            self.sell(data, size=size)

class MomentumStrategy(bt.Strategy):
    """Original momentum strategy for comparison"""
    
    params = dict(
        mom_period=20,
        rev_period=5,
        rebalance_days=21,
        top_n=3,
    )
    
    def __init__(self):
        self.day_count = 0
        self.indicators = {}
        
        for data in self.datas:
            self.indicators[data._name] = {
                'mom': bt.indicators.RateOfChange(data.close, period=self.p.mom_period),
                'rev': bt.indicators.RateOfChange(data.close, period=self.p.rev_period),
            }
    
    def next(self):
        self.day_count += 1
        if self.day_count % self.p.rebalance_days != 0:
            return
        
        # Calculate scores
        scores = {}
        for data in self.datas:
            if len(data) < self.p.mom_period + 5:
                continue
            ind = self.indicators[data._name]
            score = ind['mom'][0] - ind['rev'][0]
            scores[data._name] = score
        
        if len(scores) < self.p.top_n:
            return
        
        # Get top N stocks
        sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_stocks = [s[0] for s in sorted_stocks[:self.p.top_n]]
        
        # Same rebalancing logic
        target_weight = 1.0 / self.p.top_n
        
        for data in self.datas:
            if data._name not in top_stocks and self.getposition(data).size > 0:
                self.close(data)
        
        for data in self.datas:
            if data._name in top_stocks:
                target_value = self.broker.getvalue() * target_weight
                current_value = self.getposition(data).size * data.close[0]
                diff = target_value - current_value
                
                if abs(diff) > self.broker.getvalue() * 0.05:
                    if diff > 0:
                        size = int(diff / data.close[0])
                        if size > 0:
                            self.buy(data, size=size)
                    else:
                        size = int(-diff / data.close[0])
                        if size > 0:
                            self.sell(data, size=size)

def run_backtest(strategy_class, strategy_name, start_date, end_date):
    """Run backtest for a strategy"""
    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy_class)
    
    # Add data feeds
    for symbol in stocks:
        stock_df = prices[prices['symbol'] == symbol].copy()
        stock_df = stock_df[(stock_df['date'] >= start_date) & (stock_df['date'] <= end_date)]
        
        if len(stock_df) < 100:
            continue
            
        stock_df = stock_df.set_index('date')
        stock_df = stock_df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'volume': 'Volume'
        })
        stock_df['OpenInterest'] = 0
        
        data = bt.feeds.PandasData(
            dataname=stock_df,
            name=symbol,
            fromdate=start_date,
            todate=end_date
        )
        cerebro.adddata(data)
    
    # Add SPY for benchmark
    spy_df = prices[prices['symbol'] == 'SPY'].copy()
    spy_df = spy_df[(spy_df['date'] >= start_date) & (spy_df['date'] <= end_date)]
    spy_start = spy_df['close'].iloc[0]
    spy_end = spy_df['close'].iloc[-1]
    spy_return = (spy_end / spy_start - 1) * 100
    
    # Settings
    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0.001)
    
    # Run
    start_value = cerebro.broker.getvalue()
    cerebro.run()
    end_value = cerebro.broker.getvalue()
    
    total_return = (end_value / start_value - 1) * 100
    
    return {
        'strategy': strategy_name,
        'start_value': start_value,
        'end_value': end_value,
        'return': total_return,
        'spy_return': spy_return,
        'alpha': total_return - spy_return
    }

# Run backtests
# Use signal period for ML strategy
signal_start = signals['date'].min()
signal_end = signals['date'].max()

print(f"\n📊 Backtest Period: {signal_start.date()} to {signal_end.date()}")

print("\n🔄 Running ML Strategy backtest...")
ml_result = run_backtest(MLSignalStrategy, "ML Signal", signal_start, signal_end)

print("🔄 Running Momentum Strategy backtest...")
mom_result = run_backtest(MomentumStrategy, "Momentum", signal_start, signal_end)

# Results
print("\n" + "=" * 60)
print("📈 RESULTS")
print("=" * 60)

print(f"\n{'Strategy':<15} {'Return':>12} {'SPY':>12} {'Alpha':>12}")
print("-" * 55)
print(f"{'ML Signal':<15} {ml_result['return']:>11.1f}% {ml_result['spy_return']:>11.1f}% {ml_result['alpha']:>11.1f}%")
print(f"{'Momentum':<15} {mom_result['return']:>11.1f}% {mom_result['spy_return']:>11.1f}% {mom_result['alpha']:>11.1f}%")

print("\n" + "=" * 60)
