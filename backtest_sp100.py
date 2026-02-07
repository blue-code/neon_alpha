#!/usr/bin/env python
"""
Backtest Momentum + ADX Defense strategy on S&P 100
"""

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("Momentum + ADX Strategy Backtest (S&P 100)")
print("=" * 60)

# Load data
prices = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_prices.csv")
prices['date'] = pd.to_datetime(prices['date'])

# Exclude ETFs for trading, keep SPY for benchmark
etfs = ['SPY', 'QQQ', 'IWM', 'DIA']
stocks = [s for s in prices['symbol'].unique() if s not in etfs]

print(f"\n📊 Data: {len(stocks)} stocks")
print(f"   Date range: {prices['date'].min().date()} to {prices['date'].max().date()}")

class MomentumADXStrategy(bt.Strategy):
    """Momentum strategy with ADX-based defense"""
    
    params = dict(
        mom_period=20,
        rev_period=5,
        adx_period=14,
        adx_threshold=25,
        rebalance_days=21,
        top_n=10,  # Top 10 for 100 stocks
        defense_mode=True,
    )
    
    def __init__(self):
        self.day_count = 0
        self.indicators = {}
        
        for data in self.datas:
            if data._name == 'SPY':
                # ADX on SPY for market regime
                self.spy_adx = bt.indicators.AverageDirectionalMovementIndex(
                    data, period=self.p.adx_period
                )
            
            self.indicators[data._name] = {
                'mom': bt.indicators.RateOfChange(data.close, period=self.p.mom_period),
                'rev': bt.indicators.RateOfChange(data.close, period=self.p.rev_period),
            }
    
    def next(self):
        self.day_count += 1
        if self.day_count % self.p.rebalance_days != 0:
            return
        
        # Check market regime (ADX)
        defense_active = False
        if self.p.defense_mode and hasattr(self, 'spy_adx'):
            if self.spy_adx.adx[0] < self.p.adx_threshold:
                defense_active = True
        
        # Calculate scores for all stocks
        scores = {}
        for data in self.datas:
            if data._name in ['SPY', 'QQQ', 'IWM', 'DIA']:
                continue
            if len(data) < self.p.mom_period + 10:
                continue
                
            ind = self.indicators[data._name]
            score = ind['mom'][0] - ind['rev'][0]
            scores[data._name] = score
        
        if len(scores) < self.p.top_n:
            return
        
        # Get top N stocks
        sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_stocks = [s[0] for s in sorted_stocks[:self.p.top_n]]
        
        # Adjust position size based on defense
        if defense_active:
            target_weight = 0.5 / self.p.top_n  # 50% invested
        else:
            target_weight = 1.0 / self.p.top_n  # 100% invested
        
        # Close positions not in top_stocks
        for data in self.datas:
            if data._name not in top_stocks and self.getposition(data).size > 0:
                self.close(data)
        
        # Open/adjust positions
        for data in self.datas:
            if data._name in top_stocks:
                target_value = self.broker.getvalue() * target_weight
                current_value = self.getposition(data).size * data.close[0]
                diff = target_value - current_value
                
                if abs(diff) > self.broker.getvalue() * 0.02:
                    if diff > 0:
                        size = int(diff / data.close[0])
                        if size > 0:
                            self.buy(data, size=size)
                    else:
                        size = int(-diff / data.close[0])
                        if size > 0:
                            self.sell(data, size=size)

class MomentumOnlyStrategy(bt.Strategy):
    """Pure momentum without defense"""
    
    params = dict(
        mom_period=20,
        rev_period=5,
        rebalance_days=21,
        top_n=10,
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
        
        scores = {}
        for data in self.datas:
            if data._name in ['SPY', 'QQQ', 'IWM', 'DIA']:
                continue
            if len(data) < self.p.mom_period + 10:
                continue
                
            ind = self.indicators[data._name]
            score = ind['mom'][0] - ind['rev'][0]
            scores[data._name] = score
        
        if len(scores) < self.p.top_n:
            return
        
        sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_stocks = [s[0] for s in sorted_stocks[:self.p.top_n]]
        
        target_weight = 1.0 / self.p.top_n
        
        for data in self.datas:
            if data._name not in top_stocks and self.getposition(data).size > 0:
                self.close(data)
        
        for data in self.datas:
            if data._name in top_stocks:
                target_value = self.broker.getvalue() * target_weight
                current_value = self.getposition(data).size * data.close[0]
                diff = target_value - current_value
                
                if abs(diff) > self.broker.getvalue() * 0.02:
                    if diff > 0:
                        size = int(diff / data.close[0])
                        if size > 0:
                            self.buy(data, size=size)
                    else:
                        size = int(-diff / data.close[0])
                        if size > 0:
                            self.sell(data, size=size)

def run_backtest(strategy_class, strategy_name, start_date, end_date, **kwargs):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy_class, **kwargs)
    
    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    
    # Add data feeds
    added_count = 0
    for symbol in stocks + ['SPY']:  # Include SPY for ADX
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
        added_count += 1
    
    # Benchmark
    spy_df = prices[prices['symbol'] == 'SPY'].copy()
    spy_df = spy_df[(spy_df['date'] >= start_date) & (spy_df['date'] <= end_date)]
    spy_return = (spy_df['close'].iloc[-1] / spy_df['close'].iloc[0] - 1) * 100
    
    # Settings
    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0.001)
    
    # Run
    start_value = cerebro.broker.getvalue()
    results = cerebro.run()
    end_value = cerebro.broker.getvalue()
    
    strat = results[0]
    drawdown = strat.analyzers.drawdown.get_analysis()
    
    total_return = (end_value / start_value - 1) * 100
    max_dd = drawdown.max.drawdown
    
    return {
        'strategy': strategy_name,
        'return': total_return,
        'spy_return': spy_return,
        'alpha': total_return - spy_return,
        'max_dd': max_dd,
        'stocks': added_count - 1,  # Exclude SPY
    }

# Test periods
periods = [
    ("Full Period (5yr)", pd.Timestamp("2020-01-01"), pd.Timestamp("2025-12-31")),
    ("2022 (Bear)", pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31")),
    ("2023-2024 (Recovery)", pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31")),
]

print("\n" + "=" * 80)

for period_name, start, end in periods:
    print(f"\n📅 {period_name}")
    print("-" * 60)
    
    # Momentum only
    mom_result = run_backtest(MomentumOnlyStrategy, "Momentum", start, end)
    
    # Momentum + ADX
    adx_result = run_backtest(MomentumADXStrategy, "Mom+ADX", start, end, defense_mode=True)
    
    print(f"{'Strategy':<15} {'Return':>12} {'SPY':>12} {'Alpha':>12} {'MDD':>10}")
    print("-" * 60)
    print(f"{'Momentum':<15} {mom_result['return']:>11.1f}% {mom_result['spy_return']:>11.1f}% {mom_result['alpha']:>11.1f}% {mom_result['max_dd']:>9.1f}%")
    print(f"{'Mom+ADX':<15} {adx_result['return']:>11.1f}% {adx_result['spy_return']:>11.1f}% {adx_result['alpha']:>11.1f}% {adx_result['max_dd']:>9.1f}%")

print("\n" + "=" * 80)
print("✅ Backtest complete!")
