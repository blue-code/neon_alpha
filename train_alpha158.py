#!/usr/bin/env python
"""
Multi-Factor Strategy inspired by Qlib's Alpha158
Combines multiple factors: Momentum, Reversal, Volatility, Volume
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

import lightgbm as lgb
from scipy.stats import spearmanr
import backtrader as bt

print("=" * 60)
print("Multi-Factor Strategy (Qlib-inspired)")
print("=" * 60)

# Load data
df = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_prices.csv")
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(['symbol', 'date']).reset_index(drop=True)

print(f"\n📁 Data: {len(df)} rows, {df['symbol'].nunique()} stocks")

# Generate Alpha158-style features
print("\n🔧 Generating Alpha158-style features...")

def generate_alpha158_features(df, symbol):
    """Generate features for a single stock"""
    mask = df['symbol'] == symbol
    close = df.loc[mask, 'close'].values
    high = df.loc[mask, 'high'].values
    low = df.loc[mask, 'low'].values
    open_p = df.loc[mask, 'open'].values
    volume = df.loc[mask, 'volume'].values
    
    n = len(close)
    features = {}
    
    # KBAR features (candlestick patterns)
    features['KMID'] = (close - open_p) / (open_p + 1e-12)
    features['KLEN'] = (high - low) / (open_p + 1e-12)
    features['KMID2'] = (close - open_p) / (high - low + 1e-12)
    features['KUP'] = (high - np.maximum(open_p, close)) / (open_p + 1e-12)
    features['KLOW'] = (np.minimum(open_p, close) - low) / (open_p + 1e-12)
    features['KSFT'] = (2*close - high - low) / (open_p + 1e-12)
    
    # Rolling features for multiple windows
    windows = [5, 10, 20, 60]
    
    for w in windows:
        # ROC (Rate of Change) - Momentum
        roc = np.full(n, np.nan)
        roc[w:] = close[w:] / close[:-w] - 1
        features[f'ROC{w}'] = roc
        
        # MA ratio
        ma = pd.Series(close).rolling(w).mean().values
        features[f'MA{w}'] = ma / close - 1
        
        # STD (Volatility)
        std = pd.Series(close).pct_change().rolling(w).std().values
        features[f'STD{w}'] = std
        
        # MAX/MIN ratio (range)
        max_h = pd.Series(high).rolling(w).max().values
        min_l = pd.Series(low).rolling(w).min().values
        features[f'MAX{w}'] = max_h / close - 1
        features[f'MIN{w}'] = min_l / close - 1
        
        # RSI
        delta = pd.Series(close).diff()
        gain = delta.where(delta > 0, 0).rolling(w).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(w).mean()
        rs = gain / (loss + 1e-12)
        features[f'RSI{w}'] = (100 - 100 / (1 + rs)).values
        
        # Volume MA ratio
        vol_ma = pd.Series(volume).rolling(w).mean().values
        features[f'VMA{w}'] = volume / (vol_ma + 1e-12) - 1
        
        # RSQR (R-squared of linear trend)
        rsqr = np.full(n, np.nan)
        for i in range(w, n):
            y = close[i-w:i]
            x = np.arange(w)
            if np.std(y) > 0:
                corr = np.corrcoef(x, y)[0, 1]
                rsqr[i] = corr ** 2
        features[f'RSQR{w}'] = rsqr
        
        # BETA (Slope of linear trend)
        beta = np.full(n, np.nan)
        for i in range(w, n):
            y = close[i-w:i]
            x = np.arange(w)
            if np.std(x) > 0:
                beta[i] = np.polyfit(x, y, 1)[0] / close[i]
        features[f'BETA{w}'] = beta
    
    # Reversal features
    for d in [3, 5, 10]:
        rev = np.full(n, np.nan)
        rev[d+1:] = close[1:-d] / close[:-d-1] - 1
        features[f'REV{d}'] = rev
    
    # Target: 5-day forward return
    target = np.full(n, np.nan)
    target[:-5] = close[5:] / close[:-5] - 1
    features['target'] = target
    
    return pd.DataFrame(features, index=df.loc[mask].index)

# Apply to all stocks
all_features = []
symbols = df['symbol'].unique()
for i, symbol in enumerate(symbols):
    if (i + 1) % 20 == 0:
        print(f"   Progress: {i+1}/{len(symbols)}")
    feat_df = generate_alpha158_features(df, symbol)
    feat_df['symbol'] = symbol
    feat_df['date'] = df.loc[df['symbol'] == symbol, 'date'].values
    all_features.append(feat_df)

result = pd.concat(all_features, ignore_index=True)

# Feature columns
feature_cols = [c for c in result.columns if c not in ['symbol', 'date', 'target']]
print(f"   Generated {len(feature_cols)} features")

# Drop NaN
result = result.dropna(subset=feature_cols + ['target'])
print(f"   Clean rows: {len(result)}")

# Split data
train_end = pd.Timestamp("2023-12-31")
valid_end = pd.Timestamp("2024-06-30")

train_df = result[result['date'] <= train_end].copy()
valid_df = result[(result['date'] > train_end) & (result['date'] <= valid_end)].copy()
test_df = result[result['date'] > valid_end].copy()

print(f"\n📊 Data splits:")
print(f"   Train: {len(train_df)} ({train_df['date'].min().date()} to {train_df['date'].max().date()})")
print(f"   Valid: {len(valid_df)}")
print(f"   Test:  {len(test_df)} ({test_df['date'].min().date()} to {test_df['date'].max().date()})")

# Train LightGBM
print("\n🤖 Training LightGBM model...")

X_train = train_df[feature_cols].values
y_train = train_df['target'].values
X_valid = valid_df[feature_cols].values
y_valid = valid_df['target'].values
X_test = test_df[feature_cols].values

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
}

model = lgb.train(
    params,
    train_data,
    num_boost_round=500,
    valid_sets=[valid_data],
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

print("\n📊 Top 15 Important Features:")
for _, row in importance.head(15).iterrows():
    print(f"   {row['feature']}: {row['importance']}")

# Predictions
test_df['pred_score'] = model.predict(X_test)
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
icir = ic_series.mean() / (ic_series.std() + 1e-12)
print(f"   ICIR: {icir:.4f}")

top10 = test_df[test_df['signal'] == 1].groupby('date')['target'].mean().mean()
all_avg = test_df.groupby('date')['target'].mean().mean()
print(f"\n   Top 10 avg 5-day return: {top10*100:.4f}%")
print(f"   All stocks avg return:  {all_avg*100:.4f}%")
print(f"   Outperformance:         {(top10-all_avg)*100:.4f}%")

# Long-Short
test_df['bottom_signal'] = (test_df['rank'] > test_df.groupby('date')['rank'].transform('max') - 10).astype(int)
top10_daily = test_df[test_df['signal'] == 1].groupby('date')['target'].mean()
bottom10_daily = test_df[test_df['bottom_signal'] == 1].groupby('date')['target'].mean()
long_short = (top10_daily - bottom10_daily).mean()
print(f"   Long-Short spread:      {long_short*100:.4f}%")

# Most selected stocks
print("\n🏆 Most frequently selected stocks:")
top_picks = test_df[test_df['signal'] == 1].groupby('symbol').size().sort_values(ascending=False)
for stock, count in top_picks.head(10).items():
    pct = count / test_df['date'].nunique() * 100
    print(f"   {stock}: {count} times ({pct:.1f}%)")

# Save
output_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/alpha158_signals.csv"
test_df[['date', 'symbol', 'pred_score', 'rank', 'signal', 'target']].to_csv(output_path, index=False)
print(f"\n💾 Signals saved to: {output_path}")

model.save_model("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/alpha158_model.txt")

print("\n" + "=" * 60)
print("✅ Alpha158 Multi-Factor training complete!")
print("=" * 60)
