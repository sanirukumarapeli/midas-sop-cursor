# location: src/risk_analyzer.py
import joblib
import pandas as pd
import numpy as np
from src.forecast import safe_encode
from src.data_query import _get_dataframe

def evaluate_fulfillment_risk(year, month, plant_name, customer_name, current_nsp):
    """Predicts statistical likelihood of operational delivery failures with batch support."""
    try:
        model = joblib.load('models/risk_model.joblib')
        encoders = joblib.load('models/label_encoders.joblib')
        df = _get_dataframe()
        
        feature_order = ['Year', 'Month', 'Plant_encoded', 'Customer_encoded', 'Net_Selling_Price']
        
        # 🚨 DETECT MACRO QUERIES
        macro_indicators = ['all', 'total', 'global', 'company', 'overall', 'unknown', '']
        is_macro_plant = str(plant_name).strip().lower() in macro_indicators
        is_macro_cust = str(customer_name).strip().lower() in macro_indicators

        if is_macro_plant or is_macro_cust:
            # --- BATCH OPERATIONAL RISK EVALUATION ---
            condition = pd.Series(True, index=df.index)
            if not is_macro_plant:
                condition &= df['Plant'].str.lower() == str(plant_name).strip().lower()
            if not is_macro_cust:
                condition &= df['Customer'].str.lower() == str(customer_name).strip().lower()
                
            filtered_df = df[condition]
            if filtered_df.empty:
                filtered_df = df
                
            batch_df = filtered_df[['Plant', 'Customer']].drop_duplicates().copy()
            batch_df['Year'] = int(year)
            batch_df['Month'] = int(month)
            
            nsp_val = float(current_nsp) if float(current_nsp) > 0 else filtered_df['Net_Selling_Price'].median()
            batch_df['Net_Selling_Price'] = nsp_val
            
            le_plant = encoders.get('Plant')
            le_cust = encoders.get('Customer')
            
            batch_df['Plant_encoded'] = batch_df['Plant'].apply(lambda x: le_plant.transform([x])[0] if le_plant and x in le_plant.classes_ else 0)
            batch_df['Customer_encoded'] = batch_df['Customer'].apply(lambda x: le_cust.transform([x])[0] if le_cust and x in le_cust.classes_ else 0)
            
            X_batch = batch_df[feature_order]
            prob_vectors = model.predict_proba(X_batch)[:, 1]
            
            mean_prob = float(np.mean(prob_vectors))
            risk_tier = "High" if mean_prob > 0.60 else "Moderate" if mean_prob > 0.30 else "Low"
            
            return {
                "probability": mean_prob,
                "risk_tier": risk_tier,
                "trigger_safety_stock": True if mean_prob > 0.60 else False,
                "primary_driver": "Cross-Network Operational Capacity Constraints",
                "summary": f"Evaluated an aggregate cross-network probability of {mean_prob:.1%} breach across {len(X_batch)} supply routes."
            }
            
        else:
            # --- STANDARD SINGLE ROUTE EXECUTION ---
            input_data = {
                'Year': int(year),
                'Month': int(month),
                'Plant_encoded': safe_encode(encoders, 'Plant', plant_name),
                'Customer_encoded': safe_encode(encoders, 'Customer', customer_name),
                'Net_Selling_Price': float(current_nsp)
            }
            
            input_df = pd.DataFrame([input_data])[feature_order]
            prob = model.predict_proba(input_df)[0][1]
            
            risk_flag = True if prob > 0.60 else False
            risk_tier = "High" if prob > 0.60 else "Moderate" if prob > 0.30 else "Low"
            
            importance_scores = model.feature_importances_
            importance_dict = dict(zip(feature_order, importance_scores))
            top_feature_raw = max(importance_dict, key=importance_dict.get)
            
            feature_business_mapping = {
                'Year': 'Macro Annual Trends',
                'Month': 'Seasonal Month-end Volatility',
                'Plant_encoded': 'Specific Factory Capacity Constraints',
                'Customer_encoded': 'Customer Ordering Behavior',
                'Net_Selling_Price': 'Pricing & Margin Priority'
            }
            
            business_driver = feature_business_mapping.get(top_feature_raw, top_feature_raw)
            
            explainable_summary = (
                f"{risk_tier} fulfillment risk detected ({prob:.1%} chance). "
                f"The primary driver causing this risk profile is {business_driver}."
            )
            
            return {
                "probability": float(prob),
                "risk_tier": risk_tier,
                "trigger_safety_stock": risk_flag,
                "primary_driver": business_driver,
                "summary": explainable_summary
            }
            
    except Exception as e:
        return {
            "probability": 0.0, 
            "risk_tier": "Unknown", 
            "trigger_safety_stock": False,
            "primary_driver": "Unknown System Error",
            "summary": "Risk analysis failed to generate a prediction due to a backend pipeline error.",
            "error": str(e)
        }