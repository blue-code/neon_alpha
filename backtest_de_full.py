#!/usr/bin/env python
"""
Full backtest for DoubleEnsemble strategy with detailed metrics
"""

import backtrader as bt
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("DoubleEnsemble Full Backtest")
print("=" * 70)

# Load data
prices = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_prices.csv")
prices['date'] = pd.to_datetime(prices['date'])

signals = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/double_ensemble_signals.csv")
signals['date'] = pd.to_datetime(signals['date'])

etfs = ['SPY', 'QQQ', 'IWM', 'DIA']
stocks = [s for s in prices['symbol'].unique() if s not in etfs]

class DoubleEnsembleStrategy(bt.Strategy):
    params = dict(
        rebalance_days=5,
        top_n=10,
    )
    
    def __init__(self):
        self.day_count = 0
        self.trade_log = []
        
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

# Setup
start = signals['date'].min()
end = signals['date'].max()

print(f"\n📅 Period: {start.date()} to {end.date()}")
print(f"📊 Stocks: {len(stocks)}")

cerebro = bt.Cerebro()
cerebro.addstrategy(DoubleEnsembleStrategy)

# Analyzers
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')

# Add data
added = 0
for symbol in stocks:
    stock_df = prices[prices['symbol'] == symbol].copy()
    stock_df = stock_df[(stock_df['date'] >= start) & (stock_df['date'] <= end)]
    
    if len(stock_df) < 50:
        continue
        
    stock_df = stock_df.set_index('date')
    stock_df = stock_df.rename(columns={
        'open': 'Open', 'high': 'High', 'low': 'Low',
        'close': 'Close', 'volume': 'Volume'
    })
    stock_df['OpenInterest'] = 0
    
    data = bt.feeds.PandasData(dataname=stock_df, name=symbol, fromdate=start, todate=end)
    cerebro.adddata(data)
    added += 1

print(f"   Added {added} stocks")

# Benchmark
spy_df = prices[prices['symbol'] == 'SPY'].copy()
spy_df = spy_df[(spy_df['date'] >= start) & (spy_df['date'] <= end)]
spy_return = (spy_df['close'].iloc[-1] / spy_df['close'].iloc[0] - 1) * 100

# Settings
initial_cash = 100000
cerebro.broker.setcash(initial_cash)
cerebro.broker.setcommission(commission=0.001)

# Run
print("\n🚀 Running backtest...")
start_value = cerebro.broker.getvalue()
results = cerebro.run()
end_value = cerebro.broker.getvalue()

strat = results[0]

# Results
print("\n" + "=" * 70)
print("📈 RESULTS")
print("=" * 70)

total_return = (end_value / start_value - 1) * 100
dd = strat.analyzers.drawdown.get_analysis()
sharpe = strat.analyzers.sharpe.get_analysis()
trades = strat.analyzers.trades.get_analysis()
sqn = strat.analyzers.sqn.get_analysis()

print(f"\n💰 Performance:")
print(f"   Initial:       ${initial_cash:,.0f}")
print(f"   Final:         ${end_value:,.0f}")
print(f"   Total Return:  {total_return:.1f}%")
print(f"   SPY Return:    {spy_return:.1f}%")
print(f"   Alpha:         {total_return - spy_return:.1f}%")

print(f"\n📉 Risk:")
print(f"   Max Drawdown:  {dd.max.drawdown:.1f}%")
print(f"   Sharpe Ratio:  {sharpe.get('sharperatio', 0) or 0:.2f}")
print(f"   SQN:           {sqn.get('sqn', 0) or 0:.2f}")

total_trades = trades.get('total', {}).get('total', 0)
won = trades.get('won', {}).get('total', 0)
lost = trades.get('lost', {}).get('total', 0)
print(f"\n📊 Trades:")
print(f"   Total Trades:  {total_trades}")
if total_trades > 0:
    print(f"   Won:           {won} ({won/total_trades*100:.1f}%)")
    print(f"   Lost:          {lost} ({lost/total_trades*100:.1f}%)")

# Monthly returns
print(f"\n📅 Period Breakdown:")
months = (end - start).days / 30
annual_return = ((1 + total_return/100) ** (12/months) - 1) * 100
print(f"   Duration:      {months:.0f} months")
print(f"   Annualized:    {annual_return:.1f}%")

print("\n" + "=" * 70)
print("✅ Backtest complete!")
print("=" * 70)
