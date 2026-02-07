#!/usr/bin/env python
"""
Train ML model on S&P 500 data (100+ stocks)
"""

import os
import sys
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

import lightgbm as lgb
from scipy.stats import spearmanr

print("=" * 60)
print("ML Model Training on S&P 500 (100+ stocks)")
print("=" * 60)

# Load data
data_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_prices.csv"
df = pd.read_csv(data_path)
df['date'] = pd.to_datetime(df['date'])

print(f"\n📁 Data: {len(df)} rows, {df['symbol'].nunique()} stocks")
print(f"   Date range: {df['date'].min().date()} to {df['date'].max().date()}")

# Generate features
print("\n🔧 Generating features...")

def generate_features(group):
    df = group.copy()
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    # Price features
    df['daily_ret'] = close.pct_change()
    df['daily_range'] = (high - low) / close
    
    # Momentum
    for n in [5, 10, 20, 60]:
        df[f'mom_{n}'] = close / close.shift(n) - 1
    
    # Reversal
    for n in [3, 5]:
        df[f'rev_{n}'] = close.shift(1) / close.shift(n+1) - 1
    
    # MA ratios
    for n in [5, 10, 20, 60]:
        df[f'ma_{n}_ratio'] = close / close.rolling(n).mean() - 1
    
    # Volatility
    for n in [5, 10, 20]:
        df[f'vol_{n}'] = close.pct_change().rolling(n).std()
    
    # Volume
    df['vol_change'] = volume / volume.shift(1) - 1
    df['vol_ma_ratio'] = volume / volume.rolling(20).mean() - 1
    
    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # Price position
    df['price_position'] = (close - low.rolling(20).min()) / (high.rolling(20).max() - low.rolling(20).min())
    
    # Target: 5-day forward return
    df['target'] = close.shift(-5) / close - 1
    
    return df

result = df.groupby('symbol').apply(generate_features, include_groups=False)
result = result.reset_index()

feature_cols = [col for col in result.columns if col not in 
                ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'target', 'level_1']]

result = result.dropna(subset=feature_cols + ['target'])
print(f"   Features: {len(feature_cols)}")
print(f"   Clean rows: {len(result)}")

# Split data
train_end = pd.Timestamp("2023-12-31")
valid_end = pd.Timestamp("2024-06-30")

train_df = result[result['date'] <= train_end]
valid_df = result[(result['date'] > train_end) & (result['date'] <= valid_end)]
test_df = result[result['date'] > valid_end]

print(f"\n📊 Data splits:")
print(f"   Train: {len(train_df)} samples ({train_df['date'].min().date()} to {train_df['date'].max().date()})")
print(f"   Valid: {len(valid_df)} samples")
print(f"   Test:  {len(test_df)} samples ({test_df['date'].min().date()} to {test_df['date'].max().date()})")

X_train = train_df[feature_cols].values
y_train = train_df['target'].values
X_valid = valid_df[feature_cols].values
y_valid = valid_df['target'].values
X_test = test_df[feature_cols].values
y_test = test_df['target'].values

# Train model
print("\n🤖 Training LightGBM model...")

train_data = lgb.Dataset(X_train, label=y_train, feature_name=feature_cols)
valid_data = lgb.Dataset(X_valid, label=y_valid, feature_name=feature_cols, reference=train_data)

params = {
    'objective': 'regression',
    'metric': 'mse',
    'boosting_type': 'gbdt',
    'learning_rate': 0.02,
    'num_leaves': 64,
    'max_depth': 8,
    'feature_fraction': 0.7,
    'bagging_fraction': 0.7,
    'bagging_freq': 5,
    'lambda_l1': 0.1,
    'lambda_l2': 0.1,
    'min_data_in_leaf': 100,
    'verbose': -1,
    'n_jobs': 4,
}

model = lgb.train(
    params,
    train_data,
    num_boost_round=1000,
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

# Evaluate
print("\n🔮 Generating predictions...")

test_df = test_df.copy()
test_df['pred_score'] = model.predict(X_test)

# Rank within each day
test_df['rank'] = test_df.groupby('date')['pred_score'].rank(ascending=False)
test_df['signal'] = (test_df['rank'] <= 10).astype(int)  # Top 10 for 100 stocks

# Metrics
print("\n📈 Evaluation:")

# IC
ic = test_df.groupby('date').apply(
    lambda x: x['pred_score'].corr(x['target']), include_groups=False
).mean()
print(f"   IC: {ic:.4f}")

# Rank IC
rank_ic = test_df.groupby('date').apply(
    lambda x: spearmanr(x['pred_score'], x['target'])[0], include_groups=False
).mean()
print(f"   Rank IC: {rank_ic:.4f}")

# ICIR (IC / std)
ic_series = test_df.groupby('date').apply(
    lambda x: x['pred_score'].corr(x['target']), include_groups=False
)
icir = ic_series.mean() / ic_series.std()
print(f"   ICIR: {icir:.4f}")

# Returns
top10_return = test_df[test_df['signal'] == 1].groupby('date')['target'].mean().mean()
all_return = test_df.groupby('date')['target'].mean().mean()
print(f"\n   Top 10 avg 5-day return: {top10_return*100:.4f}%")
print(f"   All stocks avg return:  {all_return*100:.4f}%")
print(f"   Outperformance:         {(top10_return-all_return)*100:.4f}%")

# Long-short return (top 10 vs bottom 10)
test_df['bottom_signal'] = (test_df['rank'] > test_df.groupby('date')['rank'].transform('max') - 10).astype(int)
top10_daily = test_df[test_df['signal'] == 1].groupby('date')['target'].mean()
bottom10_daily = test_df[test_df['bottom_signal'] == 1].groupby('date')['target'].mean()
long_short = (top10_daily - bottom10_daily).mean()
print(f"   Long-Short spread:      {long_short*100:.4f}%")

# Save
output_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_ml_signals.csv"
test_df[['date', 'symbol', 'pred_score', 'rank', 'signal', 'target']].to_csv(output_path, index=False)
print(f"\n💾 Signals saved to: {output_path}")

model_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_lgb_model.txt"
model.save_model(model_path)
print(f"💾 Model saved to: {model_path}")

print("\n" + "=" * 60)
print("✅ Training complete!")
print("=" * 60)
