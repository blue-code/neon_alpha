#!/usr/bin/env python
"""
Test Qlib's DoubleEnsemble model on our data
"""

import os
import sys
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("DoubleEnsemble Model Test")
print("=" * 60)

# Check if DEnsembleModel is available
try:
    from qlib.contrib.model.double_ensemble import DEnsembleModel
    print("✅ DEnsembleModel imported successfully")
except ImportError as e:
    print(f"❌ Failed to import DEnsembleModel: {e}")
    print("   Trying alternative...")
    
# Load our data
prices = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/us_prices_full.csv")
prices['date'] = pd.to_datetime(prices['date'], utc=True).dt.tz_localize(None)

print(f"\n📁 Data loaded: {len(prices)} rows")

# Generate features (same as before)
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
    
    # Target
    df['target'] = close.shift(-5) / close - 1
    
    return df

print("\n🔧 Generating features...")
result = prices.groupby('symbol').apply(generate_features, include_groups=False)
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
print(f"   Train: {len(train_df)}")
print(f"   Valid: {len(valid_df)}")
print(f"   Test:  {len(test_df)}")

X_train = train_df[feature_cols].values
y_train = train_df['target'].values
X_valid = valid_df[feature_cols].values
y_valid = valid_df['target'].values
X_test = test_df[feature_cols].values
y_test = test_df['target'].values

# Try DEnsembleModel
print("\n🤖 Training DoubleEnsemble model...")

try:
    from qlib.contrib.model.double_ensemble import DEnsembleModel
    
    model = DEnsembleModel(
        base_model="gbm",
        loss="mse",
        num_models=3,
        enable_sr=True,
        enable_fs=True,
        alpha1=1,
        alpha2=1,
        bins_sr=10,
        bins_fs=5,
        decay=0.5,
        sample_ratios=[0.8, 0.7, 0.6],
        sub_weights=[1, 1, 1],
        epochs=10,
        colsample_bytree=0.8,
        learning_rate=0.1,
        subsample=0.8,
        lambda_l1=1.0,
        lambda_l2=1.0,
        max_depth=6,
        num_leaves=32,
        num_threads=4,
        verbosity=-1
    )
    
    # DEnsembleModel expects DataFrame with specific format
    # Let's create a simple wrapper
    train_data = pd.DataFrame(X_train, columns=feature_cols)
    train_data['label'] = y_train
    
    valid_data = pd.DataFrame(X_valid, columns=feature_cols)
    valid_data['label'] = y_valid
    
    # This may not work directly, let's try the fit interface
    model.fit(train_data, valid_data)
    
    predictions = model.predict(pd.DataFrame(X_test, columns=feature_cols))
    print("✅ DoubleEnsemble training complete!")
    
except Exception as e:
    print(f"❌ DoubleEnsemble failed: {e}")
    print("\n💡 Falling back to manual ensemble with LightGBM...")
    
    import lightgbm as lgb
    
    # Manual ensemble: train multiple models with different subsamples
    predictions_list = []
    
    for i, sample_ratio in enumerate([0.8, 0.7, 0.6]):
        print(f"   Training model {i+1}/3 (sample_ratio={sample_ratio})...")
        
        # Random subsample
        n_samples = int(len(X_train) * sample_ratio)
        indices = np.random.choice(len(X_train), n_samples, replace=False)
        
        X_sub = X_train[indices]
        y_sub = y_train[indices]
        
        train_data = lgb.Dataset(X_sub, label=y_sub, feature_name=feature_cols)
        valid_data = lgb.Dataset(X_valid, label=y_valid, feature_name=feature_cols, reference=train_data)
        
        params = {
            'objective': 'regression',
            'metric': 'mse',
            'boosting_type': 'gbdt',
            'learning_rate': 0.05,
            'num_leaves': 32,
            'max_depth': 6,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'lambda_l1': 0.5,
            'lambda_l2': 0.5,
            'verbose': -1,
        }
        
        model = lgb.train(
            params,
            train_data,
            num_boost_round=200,
            valid_sets=[valid_data],
            callbacks=[
                lgb.early_stopping(stopping_rounds=30),
                lgb.log_evaluation(period=0)
            ]
        )
        
        pred = model.predict(X_test)
        predictions_list.append(pred)
        print(f"      Best iteration: {model.best_iteration}")
    
    # Ensemble: average predictions
    predictions = np.mean(predictions_list, axis=0)
    print("✅ Ensemble training complete!")

# Evaluate
test_df = test_df.copy()
test_df['pred_score'] = predictions
test_df['rank'] = test_df.groupby('date')['pred_score'].rank(ascending=False)
test_df['signal'] = (test_df['rank'] <= 3).astype(int)

# IC
ic = test_df.groupby('date').apply(
    lambda x: x['pred_score'].corr(x['target']), include_groups=False
).mean()

from scipy.stats import spearmanr
rank_ic = test_df.groupby('date').apply(
    lambda x: spearmanr(x['pred_score'], x['target'])[0], include_groups=False
).mean()

top3_return = test_df[test_df['signal'] == 1].groupby('date')['target'].mean().mean()
all_return = test_df.groupby('date')['target'].mean().mean()

print("\n📈 Evaluation:")
print(f"   IC: {ic:.4f}")
print(f"   Rank IC: {rank_ic:.4f}")
print(f"   Top 3 avg 5-day return: {top3_return*100:.4f}%")
print(f"   All stocks avg return:  {all_return*100:.4f}%")
print(f"   Outperformance:         {(top3_return-all_return)*100:.4f}%")

# Save
output_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/ensemble_signals.csv"
test_df[['date', 'symbol', 'pred_score', 'rank', 'signal', 'target']].to_csv(output_path, index=False)
print(f"\n💾 Signals saved to: {output_path}")

print("\n" + "=" * 60)
