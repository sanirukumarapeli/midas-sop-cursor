import joblib
import pandas as pd
import numpy as np
import os
from src.data_query import _get_dataframe  

def safe_encode(encoder_dict, col_name, value):
    """Safely converts human strings to trained machine integers."""
    le = encoder_dict.get(col_name)
    if not le: 
        return 0
    if value in le.classes_: 
        return le.transform([value])[0]
    if "Unknown" in le.classes_: 
        return le.transform(["Unknown"])[0]
    return 0

def run_demand_inference(year, month, manager_name, customer_name, country_name, 
                         material_name="Unknown", material_group="Unknown", 
                         is_new_customer=0, is_new_material=0, 
                         unit_price=10.0):
    """Loads weights dynamically and executes inference mapping with macro batch aggregation."""
    try:
        encoders = joblib.load('models/label_encoders.joblib')
        model_q10 = joblib.load('models/demand_model_q10.joblib')
        model_q50 = joblib.load('models/demand_model_q50.joblib')
        model_q90 = joblib.load('models/demand_model_q90.joblib')
        
        df = _get_dataframe()
        feature_order = [
            'Year', 'Month', 'Month_Sin', 'Month_Cos',
            'Regional_Sales_Manager_encoded', 'Customer_encoded', 'Country_encoded', 
            'Material_encoded', 'Material_Group1_MST_encoded',
            'Is_New_Customer', 'Is_New_Material', 'Historical_Unit_Price', 'Rolling_3M_Demand'
        ]

        # 🚨 DETECT MACRO QUERIES
        macro_indicators = ['all', 'total', 'global', 'company', 'overall', 'unknown', '']
        is_macro_cust = str(customer_name).strip().lower() in macro_indicators
        is_macro_ctry = str(country_name).strip().lower() in macro_indicators
        
        if is_macro_cust or is_macro_ctry:
            # --- 🚨 DUAL-ENGINE ROUTING: USE NEW TOP-DOWN MACRO MODEL ---
            macro_q10 = joblib.load('models/macro_model_q10.joblib')
            macro_q50 = joblib.load('models/macro_model_q50.joblib')
            macro_q90 = joblib.load('models/macro_model_q90.joblib')
            
            # 🚨 FOOLPROOF BASELINE CALCULATION 🚨
            # Instead of crashing if 'Year' or 'Month' are missing, we safely calculate the average monthly run-rate.
            total_qty = float(df['Confirmed_Quantity'].sum())
            unique_months = df['Calendar_Year_Month'].nunique() if 'Calendar_Year_Month' in df.columns else 12
            recent_macro = total_qty / max(1, unique_months)
                
            input_data = {
                'Year': int(year),
                'Month': int(month),
                'Month_Sin': float(np.sin(2 * np.pi * int(month) / 12)),
                'Month_Cos': float(np.cos(2 * np.pi * int(month) / 12)),
                'Rolling_3M_Macro': float(recent_macro)
            }
            
            input_df = pd.DataFrame([input_data])[['Year', 'Month', 'Month_Sin', 'Month_Cos', 'Rolling_3M_Macro']]
            
            pred_q10 = max(0, float(macro_q10.predict(input_df)[0]))
            pred_q50 = max(0, float(macro_q50.predict(input_df)[0]))
            pred_q90 = max(0, float(macro_q90.predict(input_df)[0]))
            
            return {
                "forecasted_units": round(pred_q50, 2), 
                "confidence_lower": round(pred_q10, 2),
                "confidence_upper": round(pred_q90, 2),
                "historical_baseline": round(recent_macro, 2),
                "ai_reasoning": "Powered by the dedicated Top-Down Macro ML Engine, capturing true company-wide seasonality trends."
            }
            
        else:
            # --- STANDARD SINGLE MICRO RUN MODE ---
            customer_history = df[df['Customer'] == customer_name]
            qty_col = 'Confirmed_Quantity'
            
            if not customer_history.empty:
                customer_history = customer_history.sort_values(by=['Year', 'Month'])
                recent_demand = customer_history[qty_col].tail(3).mean()
                calculated_rolling_demand = float(recent_demand)
            else:
                calculated_rolling_demand = float(df[qty_col].mean())
                
            month_sin = np.sin(2 * np.pi * int(month) / 12)
            month_cos = np.cos(2 * np.pi * int(month) / 12)
            
            input_data = {
                'Year': int(year), 'Month': int(month), 'Month_Sin': float(month_sin), 'Month_Cos': float(month_cos),
                'Regional_Sales_Manager_encoded': safe_encode(encoders, 'Regional_Sales_Manager', manager_name),
                'Customer_encoded': safe_encode(encoders, 'Customer', customer_name),
                'Country_encoded': safe_encode(encoders, 'Country', country_name),
                'Material_encoded': safe_encode(encoders, 'Material', material_name),
                'Material_Group1_MST_encoded': safe_encode(encoders, 'Material_Group1_MST', material_group),
                'Is_New_Customer': int(is_new_customer), 'Is_New_Material': int(is_new_material),
                'Historical_Unit_Price': float(unit_price), 'Rolling_3M_Demand': float(calculated_rolling_demand)
            }
            
            input_df = pd.DataFrame([input_data])[feature_order]
            pred_q10 = max(0, float(model_q10.predict(input_df)[0]))
            pred_q50 = max(0, float(model_q50.predict(input_df)[0]))
            pred_q90 = max(0, float(model_q90.predict(input_df)[0]))
            
            importance_scores = model_q50.feature_importances_
            importance_dict = dict(zip(feature_order, importance_scores))
            top_feature = max(importance_dict, key=importance_dict.get)
            
            return {
                "forecasted_units": round(pred_q50, 2), 
                "confidence_lower": round(pred_q10, 2),
                "confidence_upper": round(pred_q90, 2),
                "historical_baseline": round(calculated_rolling_demand, 2),
                "ai_reasoning": f"The primary algorithmic driver influencing this specific micro forecast is '{top_feature}'."
            }
            
    except Exception as e:
        return {"error": f"Pipeline Error encountered: {str(e)}"}