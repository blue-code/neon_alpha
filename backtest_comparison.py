#!/usr/bin/env python
"""
Backtest comparison: DoubleEnsemble vs Alpha158 vs Momentum
"""

import backtrader as bt
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("Strategy Comparison Backtest")
print("=" * 60)

# Load data
prices = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_prices.csv")
prices['date'] = pd.to_datetime(prices['date'])

de_signals = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/double_ensemble_signals.csv")
de_signals['date'] = pd.to_datetime(de_signals['date'])

alpha_signals = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/alpha158_signals.csv")
alpha_signals['date'] = pd.to_datetime(alpha_signals['date'])

etfs = ['SPY', 'QQQ', 'IWM', 'DIA']
stocks = [s for s in prices['symbol'].unique() if s not in etfs]

print(f"📊 Stocks: {len(stocks)}")
print(f"📅 Period: {de_signals['date'].min().date()} to {de_signals['date'].max().date()}")

class MLStrategy(bt.Strategy):
    """Strategy using ML signals"""
    
    params = dict(
        signals_df=None,
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
        date_signals = self.p.signals_df[self.p.signals_df['date'].dt.date == current_date]
        
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
            if data._name in etfs or len(data) < self.p.mom_period + 10:
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
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    
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
        
        data = bt.feeds.PandasData(dataname=stock_df, name=symbol, fromdate=start_date, todate=end_date)
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
    sharpe = strat.analyzers.sharpe.get_analysis()
    
    return {
        'strategy': strategy_name,
        'return': (end_value / start_value - 1) * 100,
        'spy_return': spy_return,
        'max_dd': dd.max.drawdown,
        'sharpe': sharpe.get('sharperatio', 0) or 0,
    }

# Test
start = de_signals['date'].min()
end = de_signals['date'].max()

print(f"\n📅 Backtest: {start.date()} to {end.date()}")
print("-" * 60)

print("\n🔄 Running DoubleEnsemble...")
de_result = run_backtest(MLStrategy, "DoubleEnsemble", start, end, signals_df=de_signals)

print("🔄 Running Alpha158...")
alpha_result = run_backtest(MLStrategy, "Alpha158", start, end, signals_df=alpha_signals)

print("🔄 Running Momentum...")
mom_result = run_backtest(MomentumStrategy, "Momentum", start, end)

# Results
print("\n" + "=" * 70)
print("📈 RESULTS")
print("=" * 70)

print(f"\n{'Strategy':<18} {'Return':>10} {'Alpha':>10} {'MDD':>10} {'Sharpe':>10}")
print("-" * 70)
for r in [de_result, alpha_result, mom_result]:
    alpha = r['return'] - r['spy_return']
    print(f"{r['strategy']:<18} {r['return']:>9.1f}% {alpha:>9.1f}% {r['max_dd']:>9.1f}% {r['sharpe']:>10.2f}")

print(f"\n{'SPY (Benchmark)':<18} {de_result['spy_return']:>9.1f}%")

print("\n" + "=" * 70)
