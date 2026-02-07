#!/usr/bin/env python
"""
Backtest Alpha158 ML signals vs Pure Momentum
"""

import backtrader as bt
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("Alpha158 ML Strategy Backtest")
print("=" * 60)

# Load data
prices = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_prices.csv")
prices['date'] = pd.to_datetime(prices['date'])

signals = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/alpha158_signals.csv")
signals['date'] = pd.to_datetime(signals['date'])

# Exclude ETFs
etfs = ['SPY', 'QQQ', 'IWM', 'DIA']
stocks = [s for s in prices['symbol'].unique() if s not in etfs]

print(f"📊 Stocks: {len(stocks)}")
print(f"📅 Signal period: {signals['date'].min().date()} to {signals['date'].max().date()}")

class Alpha158Strategy(bt.Strategy):
    """Strategy using Alpha158 ML signals"""
    
    params = dict(
        rebalance_days=5,
        top_n=10,
    )
    
    def __init__(self):
        self.day_count = 0
        
    def next(self):
        self.day_count += 1
        if self.day_count % self.p.rebalance_days != 0:
            return
        
        current_date = self.datas[0].datetime.date(0)
        date_signals = signals[signals['date'].dt.date == current_date]
        
        if len(date_signals) == 0:
            return
        
        top_stocks = date_signals.nlargest(self.p.top_n, 'pred_score')['symbol'].tolist()
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

class MomentumStrategy(bt.Strategy):
    """Pure momentum for comparison"""
    
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
            if data._name in etfs:
                continue
            if len(data) < self.p.mom_period + 10:
                continue
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
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    
    for symbol in stocks:
        stock_df = prices[prices['symbol'] == symbol].copy()
        stock_df = stock_df[(stock_df['date'] >= start_date) & (stock_df['date'] <= end_date)]
        
        if len(stock_df) < 50:
            continue
            
        stock_df = stock_df.set_index('date')
        stock_df = stock_df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'volume': 'Volume'
        })
        stock_df['OpenInterest'] = 0
        
        data = bt.feeds.PandasData(
            dataname=stock_df, name=symbol,
            fromdate=start_date, todate=end_date
        )
        cerebro.adddata(data)
    
    spy_df = prices[prices['symbol'] == 'SPY'].copy()
    spy_df = spy_df[(spy_df['date'] >= start_date) & (spy_df['date'] <= end_date)]
    spy_return = (spy_df['close'].iloc[-1] / spy_df['close'].iloc[0] - 1) * 100
    
    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0.001)
    
    start_value = cerebro.broker.getvalue()
    results = cerebro.run()
    end_value = cerebro.broker.getvalue()
    
    strat = results[0]
    dd = strat.analyzers.drawdown.get_analysis()
    
    return {
        'strategy': strategy_name,
        'return': (end_value / start_value - 1) * 100,
        'spy_return': spy_return,
        'max_dd': dd.max.drawdown,
    }

# Test period (same as signals)
start = signals['date'].min()
end = signals['date'].max()

print(f"\n📅 Backtest: {start.date()} to {end.date()}")
print("-" * 60)

# Run backtests
print("\n🔄 Running Alpha158 ML Strategy...")
ml_result = run_backtest(Alpha158Strategy, "Alpha158 ML", start, end)

print("🔄 Running Momentum Strategy...")
mom_result = run_backtest(MomentumStrategy, "Momentum", start, end)

# Results
print("\n" + "=" * 60)
print("📈 RESULTS")
print("=" * 60)

print(f"\n{'Strategy':<20} {'Return':>12} {'SPY':>12} {'Alpha':>12} {'MDD':>10}")
print("-" * 70)
for r in [ml_result, mom_result]:
    alpha = r['return'] - r['spy_return']
    print(f"{r['strategy']:<20} {r['return']:>11.1f}% {r['spy_return']:>11.1f}% {alpha:>11.1f}% {r['max_dd']:>9.1f}%")

print("\n" + "=" * 60)
