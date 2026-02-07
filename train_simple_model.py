#!/usr/bin/env python
"""
Simple ML Model for Stock Ranking
Uses our downloaded data directly (no complex Qlib handlers)
"""

import os
import sys
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import ndcg_score

print("=" * 60)
print("Stock Ranking Model Training (LightGBM)")
print("=" * 60)

# Load price data
data_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/us_prices_full.csv"
print(f"\n📁 Loading data from: {data_path}")

df = pd.read_csv(data_path)
df['date'] = pd.to_datetime(df['date'])
print(f"   Rows: {len(df)}")
print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
print(f"   Stocks: {df['symbol'].nunique()}")

# Generate features for each stock
print("\n🔧 Generating features...")

def generate_features(group):
    """Generate technical features for a single stock"""
    df = group.copy()
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    # Price-based features
    df['daily_ret'] = close.pct_change()
    df['daily_range'] = (high - low) / close
    
    # Momentum features (various lookbacks)
    for n in [5, 10, 20, 60]:
        df[f'mom_{n}'] = close / close.shift(n) - 1
    
    # Reversal features
    for n in [3, 5]:
        df[f'rev_{n}'] = close.shift(1) / close.shift(n+1) - 1
    
    # Moving average ratios
    for n in [5, 10, 20, 60]:
        df[f'ma_{n}_ratio'] = close / close.rolling(n).mean() - 1
    
    # Volatility features
    for n in [5, 10, 20]:
        df[f'vol_{n}'] = close.pct_change().rolling(n).std()
    
    # Volume features
    df['vol_change'] = volume / volume.shift(1) - 1
    df['vol_ma_ratio'] = volume / volume.rolling(20).mean() - 1
    
    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # Price relative to range
    df['price_position'] = (close - low.rolling(20).min()) / (high.rolling(20).max() - low.rolling(20).min())
    
    # Target: 5-day forward return (smoother, more predictable)
    df['target'] = close.shift(-5) / close - 1
    
    return df

# Apply to each stock
result = df.groupby('symbol').apply(generate_features, include_groups=False)
result = result.reset_index()

# Feature columns
feature_cols = [col for col in result.columns if col not in 
                ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'target', 'level_1']]

print(f"   Generated {len(feature_cols)} features")
print(f"   Features: {feature_cols[:10]}...")

# Clean data
result = result.dropna(subset=feature_cols + ['target'])
print(f"   Clean rows: {len(result)}")

# Split data
train_end = pd.Timestamp("2023-12-31").tz_localize("America/New_York")
valid_end = pd.Timestamp("2024-06-30").tz_localize("America/New_York")

train_df = result[result['date'] <= train_end]
valid_df = result[(result['date'] > train_end) & (result['date'] <= valid_end)]
test_df = result[result['date'] > valid_end]

print(f"\n📊 Data splits:")
print(f"   Train: {len(train_df)} samples ({train_df['date'].min()} to {train_df['date'].max()})")
print(f"   Valid: {len(valid_df)} samples ({valid_df['date'].min()} to {valid_df['date'].max()})")
print(f"   Test:  {len(test_df)} samples ({test_df['date'].min()} to {test_df['date'].max()})")

# Prepare data for LightGBM
X_train = train_df[feature_cols].values
y_train = train_df['target'].values

X_valid = valid_df[feature_cols].values
y_valid = valid_df['target'].values

X_test = test_df[feature_cols].values
y_test = test_df['target'].values

# Train LightGBM model
print("\n🤖 Training LightGBM model...")

train_data = lgb.Dataset(X_train, label=y_train, feature_name=feature_cols)
valid_data = lgb.Dataset(X_valid, label=y_valid, feature_name=feature_cols, reference=train_data)

params = {
    'objective': 'regression',
    'metric': 'mse',
    'boosting_type': 'gbdt',
    'learning_rate': 0.01,  # lower learning rate
    'num_leaves': 16,       # simpler model
    'max_depth': 4,
    'feature_fraction': 0.7,
    'bagging_fraction': 0.7,
    'bagging_freq': 5,
    'lambda_l1': 0.5,       # more regularization
    'lambda_l2': 0.5,
    'verbose': -1,
    'n_jobs': 4,
}

model = lgb.train(
    params,
    train_data,
    num_boost_round=500,
    valid_sets=[train_data, valid_data],
    valid_names=['train', 'valid'],
    callbacks=[
        lgb.early_stopping(stopping_rounds=50),
        lgb.log_evaluation(period=100)
    ]
)

print(f"   Best iteration: {model.best_iteration}")

# Feature importance
importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': model.feature_importance()
}).sort_values('importance', ascending=False)

print("\n📊 Top 10 Important Features:")
for _, row in importance.head(10).iterrows():
    print(f"   {row['feature']}: {row['importance']}")

# Generate predictions
print("\n🔮 Generating predictions...")

test_df = test_df.copy()
test_df['pred_score'] = model.predict(X_test)

# Rank stocks by predicted score each day
test_df['rank'] = test_df.groupby('date')['pred_score'].rank(ascending=False)

# Create trading signals (top 3 stocks)
test_df['signal'] = (test_df['rank'] <= 3).astype(int)

# Evaluate: check if predictions rank stocks well
print("\n📈 Evaluation:")

# IC (Information Coefficient) - correlation between prediction and actual return
ic = test_df.groupby('date').apply(
    lambda x: x['pred_score'].corr(x['target']), include_groups=False
).mean()
print(f"   Average IC: {ic:.4f}")

# Rank IC - Spearman correlation
from scipy.stats import spearmanr
rank_ic = test_df.groupby('date').apply(
    lambda x: spearmanr(x['pred_score'], x['target'])[0], include_groups=False
).mean()
print(f"   Average Rank IC: {rank_ic:.4f}")

# Top 3 stocks average return vs all stocks
top3_return = test_df[test_df['signal'] == 1].groupby('date')['target'].mean().mean()
all_return = test_df.groupby('date')['target'].mean().mean()
print(f"   Top 3 avg daily return: {top3_return*100:.4f}%")
print(f"   All stocks avg return:  {all_return*100:.4f}%")
print(f"   Outperformance:         {(top3_return-all_return)*100:.4f}%")

# Which stocks get selected most often
print("\n🏆 Most frequently selected stocks (test period):")
top_picks = test_df[test_df['signal'] == 1].groupby('symbol').size()
top_picks = top_picks.sort_values(ascending=False)
for stock, count in top_picks.items():
    total_days = test_df['date'].nunique()
    pct = count / total_days * 100
    print(f"   {stock}: {count} times ({pct:.1f}%)")

# Save predictions
output_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/ml_signals.csv"
test_df[['date', 'symbol', 'pred_score', 'rank', 'signal', 'target']].to_csv(output_path, index=False)
print(f"\n💾 Signals saved to: {output_path}")

# Save model
model_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/lgb_model.txt"
model.save_model(model_path)
print(f"💾 Model saved to: {model_path}")

print("\n" + "=" * 60)
print("✅ Training complete!")
print("=" * 60)
