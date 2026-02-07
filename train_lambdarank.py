#!/usr/bin/env python
"""
Train a Learning-to-Rank model for stock selection
Using LightGBM's LambdaRank objective
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

import lightgbm as lgb
from scipy.stats import spearmanr

print("=" * 60)
print("Learning to Rank Model for Stock Selection")
print("=" * 60)

# Load data
df = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_prices.csv")
df['date'] = pd.to_datetime(df['date'])

print(f"\n📁 Data: {len(df)} rows, {df['symbol'].nunique()} stocks")

# Generate features for all data at once
print("\n🔧 Generating features...")

df = df.sort_values(['symbol', 'date']).reset_index(drop=True)

for symbol in df['symbol'].unique():
    mask = df['symbol'] == symbol
    close = df.loc[mask, 'close']
    high = df.loc[mask, 'high']
    low = df.loc[mask, 'low']
    volume = df.loc[mask, 'volume']
    
    df.loc[mask, 'daily_ret'] = close.pct_change()
    df.loc[mask, 'daily_range'] = (high - low) / close
    
    for n in [5, 10, 20, 60]:
        df.loc[mask, f'mom_{n}'] = close / close.shift(n) - 1
    
    for n in [3, 5]:
        df.loc[mask, f'rev_{n}'] = close.shift(1) / close.shift(n+1) - 1
    
    for n in [5, 10, 20, 60]:
        df.loc[mask, f'ma_{n}_ratio'] = close / close.rolling(n).mean() - 1
    
    for n in [5, 10, 20]:
        df.loc[mask, f'vol_{n}'] = close.pct_change().rolling(n).std()
    
    df.loc[mask, 'vol_change'] = volume / volume.shift(1) - 1
    df.loc[mask, 'vol_ma_ratio'] = volume / volume.rolling(20).mean() - 1
    
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df.loc[mask, 'rsi_14'] = 100 - (100 / (1 + rs))
    
    df.loc[mask, 'price_position'] = (close - low.rolling(20).min()) / (high.rolling(20).max() - low.rolling(20).min())
    
    # Target: 5-day forward return
    df.loc[mask, 'target'] = close.shift(-5) / close - 1

feature_cols = ['daily_ret', 'daily_range', 
                'mom_5', 'mom_10', 'mom_20', 'mom_60',
                'rev_3', 'rev_5',
                'ma_5_ratio', 'ma_10_ratio', 'ma_20_ratio', 'ma_60_ratio',
                'vol_5', 'vol_10', 'vol_20',
                'vol_change', 'vol_ma_ratio',
                'rsi_14', 'price_position']

df = df.dropna(subset=feature_cols + ['target'])
print(f"   Features: {len(feature_cols)}")
print(f"   Clean rows: {len(df)}")

# Create ranking labels (quintiles within each day)
df['rank_label'] = df.groupby('date')['target'].transform(
    lambda x: pd.qcut(x, q=5, labels=False, duplicates='drop')
)
df = df.dropna(subset=['rank_label'])

# Split data
train_end = pd.Timestamp("2023-12-31")
valid_end = pd.Timestamp("2024-06-30")

train_df = df[df['date'] <= train_end].copy()
valid_df = df[(df['date'] > train_end) & (df['date'] <= valid_end)].copy()
test_df = df[df['date'] > valid_end].copy()

print(f"\n📊 Data splits:")
print(f"   Train: {len(train_df)} samples")
print(f"   Valid: {len(valid_df)} samples")
print(f"   Test:  {len(test_df)} samples")

# Sort by date for proper query groups
train_df = train_df.sort_values('date')
valid_df = valid_df.sort_values('date')
test_df = test_df.sort_values('date')

# Create query groups
train_groups = train_df.groupby('date').size().values
valid_groups = valid_df.groupby('date').size().values

X_train = train_df[feature_cols].values
y_train = train_df['rank_label'].values.astype(int)

X_valid = valid_df[feature_cols].values
y_valid = valid_df['rank_label'].values.astype(int)

X_test = test_df[feature_cols].values

# Train LambdaRank model
print("\n🤖 Training LambdaRank model...")

train_data = lgb.Dataset(X_train, label=y_train, group=train_groups, feature_name=feature_cols)
valid_data = lgb.Dataset(X_valid, label=y_valid, group=valid_groups, feature_name=feature_cols, reference=train_data)

params = {
    'objective': 'lambdarank',
    'metric': 'ndcg',
    'ndcg_eval_at': [5, 10],
    'boosting_type': 'gbdt',
    'learning_rate': 0.05,
    'num_leaves': 64,
    'max_depth': 8,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_data_in_leaf': 50,
    'verbose': -1,
    'n_jobs': 4,
}

model = lgb.train(
    params,
    train_data,
    num_boost_round=500,
    valid_sets=[valid_data],
    valid_names=['valid'],
    callbacks=[
        lgb.early_stopping(stopping_rounds=30),
        lgb.log_evaluation(period=50)
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

test_df['pred_score'] = model.predict(X_test)

# Rank within each day
test_df['rank'] = test_df.groupby('date')['pred_score'].rank(ascending=False)
test_df['signal'] = (test_df['rank'] <= 10).astype(int)

# Metrics
print("\n📈 Evaluation:")

ic = test_df.groupby('date').apply(
    lambda x: x['pred_score'].corr(x['target']), include_groups=False
).mean()
print(f"   IC: {ic:.4f}")

rank_ic = test_df.groupby('date').apply(
    lambda x: spearmanr(x['pred_score'], x['target'])[0], include_groups=False
).mean()
print(f"   Rank IC: {rank_ic:.4f}")

ic_series = test_df.groupby('date').apply(
    lambda x: x['pred_score'].corr(x['target']), include_groups=False
)
icir = ic_series.mean() / ic_series.std()
print(f"   ICIR: {icir:.4f}")

top10_return = test_df[test_df['signal'] == 1].groupby('date')['target'].mean().mean()
all_return = test_df.groupby('date')['target'].mean().mean()
print(f"\n   Top 10 avg 5-day return: {top10_return*100:.4f}%")
print(f"   All stocks avg return:  {all_return*100:.4f}%")
print(f"   Outperformance:         {(top10_return-all_return)*100:.4f}%")

test_df['bottom_signal'] = (test_df['rank'] > test_df.groupby('date')['rank'].transform('max') - 10).astype(int)
top10_daily = test_df[test_df['signal'] == 1].groupby('date')['target'].mean()
bottom10_daily = test_df[test_df['bottom_signal'] == 1].groupby('date')['target'].mean()
long_short = (top10_daily - bottom10_daily).mean()
print(f"   Long-Short spread:      {long_short*100:.4f}%")

# Save
output_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_rank_signals.csv"
test_df[['date', 'symbol', 'pred_score', 'rank', 'signal', 'target']].to_csv(output_path, index=False)
print(f"\n💾 Signals saved to: {output_path}")

model_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_rank_model.txt"
model.save_model(model_path)
print(f"💾 Model saved to: {model_path}")

print("\n" + "=" * 60)
print("✅ LambdaRank training complete!")
print("=" * 60)
