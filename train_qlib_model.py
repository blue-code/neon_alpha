#!/usr/bin/env python
"""
Qlib ML Model Training Script
- Uses Alpha158 feature handler (158 technical indicators)
- LightGBM model for stock ranking
- Generates trading signals for momentum strategy
"""

import os
import sys
import warnings
warnings.filterwarnings('ignore')

# Qlib requires this for multiprocessing on macOS
if __name__ == '__main__':
    import qlib
    from qlib.config import REG_US
    from qlib.data.dataset import DatasetH
    from qlib.data.dataset.handler import DataHandlerLP
    from qlib.contrib.data.handler import Alpha158
    from qlib.contrib.model.gbdt import LGBModel
    from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy
    from qlib.utils import init_instance_by_config
    import pandas as pd
    import numpy as np
    
    print("=" * 60)
    print("Qlib ML Model Training")
    print("=" * 60)
    
    # Initialize Qlib with US market data (our custom downloaded data)
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/us_data_custom/")
    print(f"\n📁 Data path: {provider_uri}")
    
    qlib.init(provider_uri=provider_uri, region=REG_US)
    print("✅ Qlib initialized")
    
    # Define our universe (top tech stocks we've been testing)
    UNIVERSE = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", 
                "META", "TSLA", "AMD", "AVGO", "NFLX"]
    
    # Time periods
    TRAIN_START = "2020-01-01"
    TRAIN_END = "2023-12-31"
    VALID_START = "2024-01-01"
    VALID_END = "2024-06-30"
    TEST_START = "2024-07-01"
    TEST_END = "2025-01-31"
    
    print(f"\n📅 Training period: {TRAIN_START} to {TRAIN_END}")
    print(f"📅 Validation period: {VALID_START} to {VALID_END}")
    print(f"📅 Test period: {TEST_START} to {TEST_END}")
    print(f"📊 Universe: {len(UNIVERSE)} stocks")
    
    # Create Alpha158 handler config
    # Alpha158 generates 158 technical features including:
    # - Price/Volume features (KMID, KLOW, KHIGH, etc.)
    # - Moving averages (MA5, MA10, MA20, MA30, MA60)
    # - Volatility (STD5, STD10, STD20, etc.)
    # - Momentum (ROC5, ROC10, ROC20, etc.)
    # - And many more...
    
    data_handler_config = {
        "start_time": TRAIN_START,
        "end_time": TEST_END,
        "fit_start_time": TRAIN_START,
        "fit_end_time": TRAIN_END,
        "instruments": UNIVERSE,
        "infer_processors": [
            {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
            {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
        ],
        "learn_processors": [
            {"class": "DropnaLabel"},
            {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}},
        ],
        "label": ["Ref($close, -2) / Ref($close, -1) - 1"],  # 1-day forward return
    }
    
    print("\n🔧 Creating Alpha158 data handler...")
    
    try:
        handler = Alpha158(**data_handler_config)
        print("✅ Alpha158 handler created")
    except Exception as e:
        print(f"❌ Error creating handler: {e}")
        print("\n💡 Let's try a simpler approach with custom features...")
        
        # Fallback: Use basic DataHandlerLP with simpler features
        from qlib.data.dataset.handler import DataHandlerLP
        
        # Simpler feature set that should work
        simple_fields = [
            # Price features
            "($close-$open)/$open",  # daily return
            "($high-$low)/$close",   # daily range
            "$volume/$ref($volume,1)-1",  # volume change
            # Momentum
            "$close/$ref($close,5)-1",   # 5-day momentum
            "$close/$ref($close,10)-1",  # 10-day momentum
            "$close/$ref($close,20)-1",  # 20-day momentum
            # Moving averages
            "mean($close,5)/$close-1",   # MA5 ratio
            "mean($close,10)/$close-1",  # MA10 ratio
            "mean($close,20)/$close-1",  # MA20 ratio
            # Volatility
            "std($close,5)/$close",      # 5-day volatility
            "std($close,20)/$close",     # 20-day volatility
        ]
        
        simple_names = [
            "daily_ret", "daily_range", "vol_chg",
            "mom_5", "mom_10", "mom_20",
            "ma5_ratio", "ma10_ratio", "ma20_ratio",
            "vol_5", "vol_20"
        ]
        
        data_handler_config = {
            "start_time": TRAIN_START,
            "end_time": TEST_END,
            "fit_start_time": TRAIN_START,
            "fit_end_time": TRAIN_END,
            "instruments": UNIVERSE,
            "infer_processors": [
                {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
            ],
            "learn_processors": [
                {"class": "DropnaLabel"},
            ],
            "data_loader": {
                "class": "QlibDataLoader",
                "kwargs": {
                    "config": {
                        "feature": (simple_fields, simple_names),
                        "label": (["Ref($close, -1) / $close - 1"], ["label"]),
                    }
                }
            }
        }
        
        handler = DataHandlerLP(**data_handler_config)
        print("✅ Simple handler created with 11 features")
    
    # Create dataset
    print("\n📊 Creating dataset...")
    
    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": handler,
            "segments": {
                "train": (TRAIN_START, TRAIN_END),
                "valid": (VALID_START, VALID_END),
                "test": (TEST_START, TEST_END),
            },
        },
    }
    
    dataset = init_instance_by_config(dataset_config)
    print("✅ Dataset created")
    
    # Get data info
    train_df = dataset.prepare("train", col_set=["feature", "label"])
    valid_df = dataset.prepare("valid", col_set=["feature", "label"])
    test_df = dataset.prepare("test", col_set=["feature", "label"])
    
    print(f"\n📈 Data shapes:")
    print(f"   Train: {train_df.shape}")
    print(f"   Valid: {valid_df.shape}")
    print(f"   Test:  {test_df.shape}")
    
    # Train LightGBM model
    print("\n🤖 Training LightGBM model...")
    
    model_config = {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": {
            "loss": "mse",
            "colsample_bytree": 0.8,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "lambda_l1": 0.1,
            "lambda_l2": 0.1,
            "max_depth": 6,
            "num_leaves": 32,
            "num_threads": 4,
            "early_stopping_rounds": 50,
            "num_boost_round": 500,
        },
    }
    
    model = init_instance_by_config(model_config)
    
    # Fit model
    model.fit(dataset)
    print("✅ Model trained!")
    
    # Generate predictions
    print("\n🔮 Generating predictions...")
    
    pred = model.predict(dataset)
    print(f"   Predictions shape: {pred.shape}")
    
    # Convert to trading signals
    print("\n📤 Creating trading signals...")
    
    # Reset index to get datetime and instrument as columns
    signals = pred.reset_index()
    signals.columns = ['datetime', 'instrument', 'score']
    
    # Rank stocks by score each day (higher is better)
    signals['rank'] = signals.groupby('datetime')['score'].rank(ascending=False)
    
    # Create signal: 1 for top 3, 0 for others
    signals['signal'] = (signals['rank'] <= 3).astype(int)
    
    # Save to CSV
    output_path = "/Volumes/SSD/DEV_SSD/MY/neon_alpha/data/qlib_signals.csv"
    signals.to_csv(output_path, index=False)
    print(f"✅ Signals saved to: {output_path}")
    
    # Show sample
    print("\n📋 Sample signals (last 10 days):")
    recent = signals[signals['datetime'] >= signals['datetime'].max() - pd.Timedelta(days=10)]
    print(recent.to_string(index=False))
    
    # Summary stats
    print("\n📊 Signal Statistics:")
    print(f"   Total predictions: {len(signals)}")
    print(f"   Date range: {signals['datetime'].min()} to {signals['datetime'].max()}")
    print(f"   Unique dates: {signals['datetime'].nunique()}")
    print(f"   Stocks per day: {len(UNIVERSE)}")
    
    # Show which stocks got selected most often
    top_picks = signals[signals['signal'] == 1].groupby('instrument').size()
    top_picks = top_picks.sort_values(ascending=False)
    print("\n🏆 Most frequently selected stocks:")
    for stock, count in top_picks.items():
        pct = count / signals['datetime'].nunique() * 100
        print(f"   {stock}: {count} times ({pct:.1f}%)")
    
    print("\n" + "=" * 60)
    print("✅ Qlib ML training complete!")
    print("=" * 60)
