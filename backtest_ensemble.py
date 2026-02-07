#!/usr/bin/env python
"""
Ensemble Strategy: Combine ML and Momentum signals
"""

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("Ensemble Strategy: ML + Momentum")
print("=" * 60)

# Load data
prices = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/us_prices_full.csv")
prices['date'] = pd.to_datetime(prices['date'], utc=True).dt.tz_localize(None)

signals = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/ml_signals.csv")
signals['date'] = pd.to_datetime(signals['date'], utc=True).dt.tz_localize(None)

stocks = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AMD', 'AVGO', 'NFLX']

class EnsembleStrategy(bt.Strategy):
    """Combine momentum ranking with ML score as a filter/boost"""
    
    params = dict(
        mom_period=20,
        rev_period=5,
        rebalance_days=21,
        top_n=3,
        ml_weight=0.3,  # Weight for ML score in ensemble
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
        
        current_date = self.datas[0].datetime.date(0)
        
        # Get ML signals for this date
        date_signals = signals[signals['date'].dt.date == current_date]
        ml_scores = {}
        if len(date_signals) > 0:
            for _, row in date_signals.iterrows():
                ml_scores[row['symbol']] = row['pred_score']
        
        # Calculate combined scores
        scores = {}
        for data in self.datas:
            if len(data) < self.p.mom_period + 5:
                continue
            
            ind = self.indicators[data._name]
            mom_score = ind['mom'][0] - ind['rev'][0]
            
            # Normalize ML score to similar scale as momentum
            ml_score = ml_scores.get(data._name, 0)
            
            # Combine: (1-w)*momentum + w*ML
            combined = (1 - self.p.ml_weight) * mom_score + self.p.ml_weight * ml_score
            scores[data._name] = combined
        
        if len(scores) < self.p.top_n:
            return
        
        # Get top N stocks
        sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_stocks = [s[0] for s in sorted_stocks[:self.p.top_n]]
        
        # Rebalance
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

class MomentumWithMLFilter(bt.Strategy):
    """Momentum strategy but skip stocks with negative ML score"""
    
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
        
        current_date = self.datas[0].datetime.date(0)
        
        # Get ML signals
        date_signals = signals[signals['date'].dt.date == current_date]
        ml_scores = {}
        if len(date_signals) > 0:
            for _, row in date_signals.iterrows():
                ml_scores[row['symbol']] = row['pred_score']
        
        # Calculate momentum scores, but filter by ML
        scores = {}
        for data in self.datas:
            if len(data) < self.p.mom_period + 5:
                continue
            
            # Skip if ML score is negative (predicts decline)
            ml_score = ml_scores.get(data._name, 0)
            if ml_score < 0:
                continue
                
            ind = self.indicators[data._name]
            score = ind['mom'][0] - ind['rev'][0]
            scores[data._name] = score
        
        if len(scores) < self.p.top_n:
            # Fall back to momentum only if not enough passed filter
            for data in self.datas:
                if data._name not in scores and len(data) >= self.p.mom_period + 5:
                    ind = self.indicators[data._name]
                    scores[data._name] = ind['mom'][0] - ind['rev'][0]
        
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
                
                if abs(diff) > self.broker.getvalue() * 0.05:
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
    
    spy_df = prices[prices['symbol'] == 'SPY'].copy()
    spy_df = spy_df[(spy_df['date'] >= start_date) & (spy_df['date'] <= end_date)]
    spy_return = (spy_df['close'].iloc[-1] / spy_df['close'].iloc[0] - 1) * 100
    
    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0.001)
    
    start_value = cerebro.broker.getvalue()
    cerebro.run()
    end_value = cerebro.broker.getvalue()
    
    total_return = (end_value / start_value - 1) * 100
    
    return {
        'strategy': strategy_name,
        'return': total_return,
        'spy_return': spy_return,
        'alpha': total_return - spy_return
    }

# Test period
signal_start = signals['date'].min()
signal_end = signals['date'].max()

print(f"\n📊 Backtest Period: {signal_start.date()} to {signal_end.date()}\n")

# Test different strategies
from backtest_ml_signals import MLSignalStrategy, MomentumStrategy

strategies = [
    (MomentumStrategy, "Momentum Only", {}),
    (MLSignalStrategy, "ML Only", {}),
    (EnsembleStrategy, "Ensemble (30% ML)", {'ml_weight': 0.3}),
    (EnsembleStrategy, "Ensemble (50% ML)", {'ml_weight': 0.5}),
    (MomentumWithMLFilter, "Momentum + ML Filter", {}),
]

results = []
for strategy_class, name, kwargs in strategies:
    print(f"🔄 {name}...", end=" ", flush=True)
    result = run_backtest(strategy_class, name, signal_start, signal_end, **kwargs)
    results.append(result)
    print(f"✓ {result['return']:.1f}%")

print("\n" + "=" * 60)
print("📈 RESULTS")
print("=" * 60)

print(f"\n{'Strategy':<25} {'Return':>12} {'SPY':>12} {'Alpha':>12}")
print("-" * 65)
for r in sorted(results, key=lambda x: x['return'], reverse=True):
    print(f"{r['strategy']:<25} {r['return']:>11.1f}% {r['spy_return']:>11.1f}% {r['alpha']:>11.1f}%")

print("\n" + "=" * 60)
