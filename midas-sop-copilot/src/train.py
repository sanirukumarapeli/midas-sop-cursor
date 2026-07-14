import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib
import os
import gc
from src.data_query import _get_dataframe # <-- NEW: Import from DB

def optimize_memory_types(df):
    """Downcasts numerical allocations to preserve RAM on 8GB laptops."""
    print("  -> Optimizing memory profiles...")
    for col in df.select_dtypes(include=['int64']).columns:
        df[col] = df[col].astype('int32')
    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = df[col].astype('float32')
    return df

def load_and_preprocess_data(models_dir):
    print("Ingesting bulk data layer from Live Database...")
    df = _get_dataframe()
    
    print("Processing time features...")
    # UPDATED SCHEMA NAMES
    df['Calendar_Year_Month'] = pd.to_datetime(df['Calendar_Year_Month'].astype(str), format='%Y%m')
    df['Year'] = df['Calendar_Year_Month'].dt.year.astype('int32')
    df['Month'] = df['Calendar_Year_Month'].dt.month.astype('int32')
    
    # Advanced Temporal & Financial Feature Engineering
    df['Month_Sin'] = np.sin(2 * np.pi * df['Month'] / 12).astype('float32')
    df['Month_Cos'] = np.cos(2 * np.pi * df['Month'] / 12).astype('float32')
    
    # UPDATED SCHEMA NAMES
    df['Is_New_Customer'] = df['New_Bus_Customer_Indicator'].apply(lambda x: 1 if str(x).strip().upper() == 'Y' else 0).astype('int32')
    df['Is_New_Material'] = df['New_Bus_Material_Indicator'].apply(lambda x: 1 if str(x).strip().upper() == 'Y' else 0).astype('int32')
    df['Historical_Unit_Price'] = (df['Confirmed_Value'] / (df['Confirmed_Quantity'] + 1)).astype('float32')

    # Custom operational bottleneck target metric
    df['Fulfillment_Gap'] = df['Confirmed_Quantity'] - df['Billing_Quantity']
    df['Gap_Percentage'] = df['Fulfillment_Gap'] / df['Confirmed_Quantity'].replace(0, 1)
    
    # 🚨 THE DATA SCIENCE FIX: Dynamic Anomaly Thresholding
    # Mathematically isolate the worst 5% of historical shipments to act as our training anomalies
    dynamic_threshold = df['Gap_Percentage'].quantile(0.95)
    
    # Failsafe: Ensure the threshold is at least a 1% gap so we never flag perfect shipments
    actual_threshold = max(float(dynamic_threshold), 0.01)
    print(f" 📈 Dynamic Risk Threshold calibrated at: {actual_threshold:.1%} gap.")
    
    # Apply the label
    df['Risk_Label'] = np.where(df['Gap_Percentage'] >= actual_threshold, 1, 0).astype('int32')
    
    print("Encoding categorical matrices...")
    # UPDATED SCHEMA NAMES
    categorical_cols = ['Regional_Sales_Manager', 'Customer', 'Country', 'Plant', 'Material', 'Material_Group1_MST']
    label_encoders = {}
    
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").astype(str)
            le = LabelEncoder()
            df[f'{col}_encoded'] = le.fit_transform(df[col]).astype('int32')
            label_encoders[col] = le
            
    joblib.dump(label_encoders, os.path.join(models_dir, 'label_encoders.joblib'))
    
    print("Applying Time-Series Sequence & Lag Features...")
    df = df.sort_values(by=['Year', 'Month']).reset_index(drop=True)
    
    if 'Material' in df.columns:
        df['Rolling_3M_Demand'] = df.groupby('Material')['Confirmed_Quantity'].transform(lambda x: x.rolling(window=3, min_periods=1).mean())
        df['Rolling_3M_Demand'] = df['Rolling_3M_Demand'].fillna(df['Confirmed_Quantity'].mean()).astype('float32')

    df = optimize_memory_types(df)
    return df

def train_and_serialize_models():
    models_dir = 'models'
    os.makedirs(models_dir, exist_ok=True)
    df = load_and_preprocess_data(models_dir)
    
    print("\n--- Training Demand Forecasting Engine (Quantile Intervals) ---")
    
    # UPDATED SCHEMA NAMES
    features_demand = [
        'Year', 'Month', 'Month_Sin', 'Month_Cos',
        'Regional_Sales_Manager_encoded', 'Customer_encoded', 'Country_encoded', 
        'Material_encoded', 'Material_Group1_MST_encoded',
        'Is_New_Customer', 'Is_New_Material', 'Historical_Unit_Price', 'Rolling_3M_Demand'
    ]
    features_demand = [f for f in features_demand if f in df.columns]
    
    X_d = df[features_demand]
    y_d = df['Confirmed_Quantity'].fillna(0)
    
    quantiles = {
        'q10': 0.10, 
        'q50': 0.50, 
        'q90': 0.90  
    }
    
    print("🚀 Training Quantile Regression Bounds...")
    for q_name, alpha in quantiles.items():
        quantile_model = xgb.XGBRegressor(
            objective='reg:quantileerror', 
            quantile_alpha=alpha, 
            tree_method='hist', 
            n_estimators=150,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        quantile_model.fit(X_d, y_d)
        joblib.dump(quantile_model, os.path.join(models_dir, f'demand_model_{q_name}.joblib'))
        print(f"  -> Saved {q_name} boundary model (Alpha={alpha})")
    
    print("\n--- Training Top-Down Macro (Company-Wide) Forecasting Engine ---")
    # 1. Aggregate the pure historical timeline
    macro_df = df.groupby(['Year', 'Month']).agg({'Confirmed_Quantity': 'sum'}).reset_index()
    macro_df = macro_df.sort_values(by=['Year', 'Month'])
    
    # 2. Add time-series seasonality features
    macro_df['Month_Sin'] = np.sin(2 * np.pi * macro_df['Month'] / 12).astype('float32')
    macro_df['Month_Cos'] = np.cos(2 * np.pi * macro_df['Month'] / 12).astype('float32')
    macro_df['Rolling_3M_Macro'] = macro_df['Confirmed_Quantity'].rolling(window=3, min_periods=1).mean().fillna(macro_df['Confirmed_Quantity'].mean())
    
    macro_features = ['Year', 'Month', 'Month_Sin', 'Month_Cos', 'Rolling_3M_Macro']
    X_m = macro_df[macro_features]
    y_m = macro_df['Confirmed_Quantity']
    
    print("🚀 Training Macro Quantile Regression Bounds...")
    for q_name, alpha in quantiles.items():
        macro_model = xgb.XGBRegressor(
            objective='reg:quantileerror', 
            quantile_alpha=alpha, 
            tree_method='hist',
            n_estimators=100,
            max_depth=4,       # Shallower depth prevents overfitting on aggregate data
            learning_rate=0.1,
            random_state=42
        )
        macro_model.fit(X_m, y_m)
        joblib.dump(macro_model, os.path.join(models_dir, f'macro_model_{q_name}.joblib'))
        print(f"  -> Saved Macro {q_name} boundary model")
    
    del X_d, y_d
    gc.collect()
    
    print("\n--- Training Supply Risk Classifier ---")
    # UPDATED SCHEMA NAMES
    features_risk = ['Year', 'Month', 'Plant_encoded', 'Customer_encoded', 'Net_Selling_Price']
    X_r = df[features_risk].copy()
    X_r['Net_Selling_Price'] = X_r['Net_Selling_Price'].fillna(X_r['Net_Selling_Price'].median())
    y_r = df['Risk_Label']
    
    X_train_r, X_test_r, y_train_r, y_test_r = train_test_split(X_r, y_r, test_size=0.2, random_state=42)
    
    neg_class_count = (y_train_r == 0).sum()
    pos_class_count = (y_train_r == 1).sum()
    
    print(f"\n📊 Risk Data Distribution -> Successes: {neg_class_count:,} | Failures: {pos_class_count:,}")
    
    if pos_class_count > 0:
        scale_weight = float(neg_class_count / pos_class_count)
        print(f"⚠️ Class Imbalance Detected. Applying Positive Scaling Weight: {scale_weight:.2f}")
    else:
        scale_weight = 1.0
        print("🚨 FATAL WARNING: 0 failures found in training data! The risk model will be completely blind.")

    risk_model = xgb.XGBClassifier(
        n_estimators=100, 
        max_depth=5, 
        learning_rate=0.1, 
        scale_pos_weight=scale_weight, 
        tree_method='hist', 
        n_jobs=-1,
        eval_metric='logloss' 
    )
    risk_model.fit(X_train_r, y_train_r)
    joblib.dump(risk_model, os.path.join(models_dir, 'risk_model.joblib'))
    
    print("\n✅ SUCCESS: All models serialized safely into /models directory.")

if __name__ == '__main__':
    train_and_serialize_models()