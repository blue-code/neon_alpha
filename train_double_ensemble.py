#!/usr/bin/env python
"""
DoubleEnsemble Strategy - Qlib's best performing model
Combines sample reweighting + feature selection across multiple LightGBM models
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

import lightgbm as lgb
from scipy.stats import spearmanr

print("=" * 60)
print("DoubleEnsemble Strategy (Qlib's Top Model)")
print("=" * 60)

# Load data
df = pd.read_csv("/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/sp500_prices.csv")
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(['symbol', 'date']).reset_index(drop=True)

print(f"\n📁 Data: {len(df)} rows, {df['symbol'].nunique()} stocks")

# Generate Alpha158-style features
print("\n🔧 Generating features...")

def generate_features(df, symbol):
    """Generate features for a single stock"""
    mask = df['symbol'] == symbol
    close = df.loc[mask, 'close'].values
    high = df.loc[mask, 'high'].values
    low = df.loc[mask, 'low'].values
    open_p = df.loc[mask, 'open'].values
    volume = df.loc[mask, 'volume'].values
    
    n = len(close)
    features = {}
    
    # KBAR features
    features['KMID'] = (close - open_p) / (open_p + 1e-12)
    features['KLEN'] = (high - low) / (open_p + 1e-12)
    features['KMID2'] = (close - open_p) / (high - low + 1e-12)
    features['KUP'] = (high - np.maximum(open_p, close)) / (open_p + 1e-12)
    features['KLOW'] = (np.minimum(open_p, close) - low) / (open_p + 1e-12)
    features['KSFT'] = (2*close - high - low) / (open_p + 1e-12)
    
    windows = [5, 10, 20, 60]
    
    for w in windows:
        roc = np.full(n, np.nan)
        roc[w:] = close[w:] / close[:-w] - 1
        features[f'ROC{w}'] = roc
        
        ma = pd.Series(close).rolling(w).mean().values
        features[f'MA{w}'] = ma / close - 1
        
        std = pd.Series(close).pct_change().rolling(w).std().values
        features[f'STD{w}'] = std
        
        max_h = pd.Series(high).rolling(w).max().values
        min_l = pd.Series(low).rolling(w).min().values
        features[f'MAX{w}'] = max_h / close - 1
        features[f'MIN{w}'] = min_l / close - 1
        
        delta = pd.Series(close).diff()
        gain = delta.where(delta > 0, 0).rolling(w).mean()
        loss_val = (-delta.where(delta < 0, 0)).rolling(w).mean()
        rs = gain / (loss_val + 1e-12)
        features[f'RSI{w}'] = (100 - 100 / (1 + rs)).values
        
        vol_ma = pd.Series(volume).rolling(w).mean().values
        features[f'VMA{w}'] = volume / (vol_ma + 1e-12) - 1
        
        rsqr = np.full(n, np.nan)
        beta = np.full(n, np.nan)
        for i in range(w, n):
            y = close[i-w:i]
            x = np.arange(w)
            if np.std(y) > 0:
                corr = np.corrcoef(x, y)[0, 1]
                rsqr[i] = corr ** 2
                beta[i] = np.polyfit(x, y, 1)[0] / close[i]
        features[f'RSQR{w}'] = rsqr
        features[f'BETA{w}'] = beta
    
    for d in [3, 5, 10]:
        rev = np.full(n, np.nan)
        rev[d+1:] = close[1:-d] / close[:-d-1] - 1
        features[f'REV{d}'] = rev
    
    features['target'] = np.concatenate([close[5:] / close[:-5] - 1, [np.nan]*5])
    
    return pd.DataFrame(features, index=df.loc[mask].index)

all_features = []
symbols = df['symbol'].unique()
for i, symbol in enumerate(symbols):
    if (i + 1) % 20 == 0:
        print(f"   Progress: {i+1}/{len(symbols)}")
    feat_df = generate_features(df, symbol)
    feat_df['symbol'] = symbol
    feat_df['date'] = df.loc[df['symbol'] == symbol, 'date'].values
    all_features.append(feat_df)

result = pd.concat(all_features, ignore_index=True)

feature_cols = [c for c in result.columns if c not in ['symbol', 'date', 'target']]
result = result.dropna(subset=feature_cols + ['target'])
print(f"   Generated {len(feature_cols)} features")
print(f"   Clean rows: {len(result)}")

# Split data
train_end = pd.Timestamp("2023-12-31")
valid_end = pd.Timestamp("2024-06-30")

train_df = result[result['date'] <= train_end].copy()
valid_df = result[(result['date'] > train_end) & (result['date'] <= valid_end)].copy()
test_df = result[result['date'] > valid_end].copy()

print(f"\n📊 Data splits:")
print(f"   Train: {len(train_df)}")
print(f"   Valid: {len(valid_df)}")
print(f"   Test:  {len(test_df)}")

# DoubleEnsemble implementation
class DoubleEnsemble:
    """Simplified DoubleEnsemble model"""
    
    def __init__(self, num_models=3, bins_sr=10, bins_fs=5, decay=0.5):
        self.num_models = num_models
        self.bins_sr = bins_sr
        self.bins_fs = bins_fs
        self.decay = decay
        self.models = []
        self.feature_subsets = []
        self.weights_history = []
        
    def fit(self, X_train, y_train, X_valid, y_valid, feature_names):
        N, F = X_train.shape
        weights = np.ones(N)
        features_mask = np.ones(F, dtype=bool)
        current_features = list(range(F))
        
        predictions = np.zeros((N, self.num_models))
        
        for k in range(self.num_models):
            print(f"\n   🔹 Sub-model {k+1}/{self.num_models}")
            print(f"      Features: {sum(features_mask)}, Samples: {N}")
            
            # Train sub-model
            X_sub = X_train[:, features_mask]
            X_val_sub = X_valid[:, features_mask]
            
            train_data = lgb.Dataset(X_sub, label=y_train, weight=weights)
            valid_data = lgb.Dataset(X_val_sub, label=y_valid, reference=train_data)
            
            params = {
                'objective': 'mse',
                'boosting_type': 'gbdt',
                'learning_rate': 0.05,
                'num_leaves': 64,
                'max_depth': 8,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'lambda_l1': 0.1,
                'lambda_l2': 0.1,
                'min_data_in_leaf': 50,
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
            
            print(f"      Best iteration: {model.best_iteration}")
            
            self.models.append(model)
            self.feature_subsets.append(features_mask.copy())
            
            # Predictions
            predictions[:, k] = model.predict(X_sub)
            
            if k + 1 == self.num_models:
                break
            
            # Ensemble prediction so far
            pred_ensemble = predictions[:, :k+1].mean(axis=1)
            
            # Calculate loss for each sample
            loss_values = (y_train - pred_ensemble) ** 2
            
            # Sample Reweighting (SR)
            # Higher weight for harder samples
            loss_bins = pd.qcut(loss_values, q=self.bins_sr, labels=False, duplicates='drop')
            bin_weights = np.arange(1, self.bins_sr + 1) / self.bins_sr
            weights = np.array([bin_weights[min(b, len(bin_weights)-1)] for b in loss_bins])
            weights = weights / weights.mean()  # normalize
            
            # Feature Selection (FS)
            # Keep features with higher importance
            importance = model.feature_importance()
            # Expand to full feature set
            full_importance = np.zeros(F)
            full_importance[features_mask] = importance
            
            # Select top features based on importance
            threshold = np.percentile(importance, 100 * (1 - 0.8 ** (k+1)))
            features_mask = full_importance >= threshold
            features_mask = features_mask | (np.random.rand(F) < 0.3)  # random keep some
            
            if features_mask.sum() < 10:
                features_mask = np.ones(F, dtype=bool)
                
        print(f"\n   ✅ Trained {self.num_models} sub-models")
        
    def predict(self, X):
        predictions = []
        for model, features_mask in zip(self.models, self.feature_subsets):
            X_sub = X[:, features_mask]
            pred = model.predict(X_sub)
            predictions.append(pred)
        return np.mean(predictions, axis=0)

# Train DoubleEnsemble
print("\n🤖 Training DoubleEnsemble...")

X_train = train_df[feature_cols].values
y_train = train_df['target'].values
X_valid = valid_df[feature_cols].values
y_valid = valid_df['target'].values
X_test = test_df[feature_cols].values

de_model = DoubleEnsemble(num_models=3, bins_sr=10, bins_fs=5)
de_model.fit(X_train, y_train, X_valid, y_valid, feature_cols)

# Predictions
print("\n🔮 Generating predictions...")
test_df['pred_score'] = de_model.predict(X_test)
test_df['rank'] = test_df.groupby('date')['pred_score'].rank(ascending=False)
test_df['signal'] = (test_df['rank'] <= 10).astype(int)

# Metrics
print("\n📈 DoubleEnsemble Evaluation:")

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

# Save
output_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/double_ensemble_signals.csv"
test_df[['date', 'symbol', 'pred_score', 'rank', 'signal', 'target']].to_csv(output_path, index=False)
print(f"\n💾 Signals saved to: {output_path}")

print("\n" + "=" * 60)
print("✅ DoubleEnsemble training complete!")
print("=" * 60)
