# Location: src/data_query.py
import duckdb
import pandas as pd
import os
import urllib.parse
from sqlalchemy import create_engine
from dotenv import load_dotenv

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

terminal = Console()

load_dotenv()

_DATA_CACHE = None

def _get_dataframe():
    """Loads data dynamically from AWS RDS MSSQL, cleans headers, and ensures numeric types for math."""
    global _DATA_CACHE
    if _DATA_CACHE is None:
        driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
        server = os.getenv("DB_SERVER", "midas-rds-dev.c4uiuoljkhl1.ap-southeast-1.rds.amazonaws.com")
        database = os.getenv("DB_NAME", "DevPracticeDb")
        user = os.getenv("DB_USER", "")
        password = os.getenv("DB_PASS", "")

        # CRITICAL SAFETY FIX: URL-Encode the password to handle the '#' character safely
        encoded_password = urllib.parse.quote_plus(password)

        # Build secure SQLAlchemy connection string (TrustServerCertificate=yes handles AWS SSL)
        conn_str = f"mssql+pyodbc://{user}:{encoded_password}@{server}/{database}?driver={driver}&TrustServerCertificate=yes"

        try:
            engine = create_engine(conn_str)
            # Pull the live table directly from the AWS RDS MSSQL instance
            df = pd.read_sql_table("sop_data", con=engine, schema="dbo")
            
            # Ensure column names are strictly stripped of whitespace (Safety Net)
            df.columns = df.columns.str.strip()

            # Force numeric types for math columns (Prevents string summation errors)
            numeric_cols = ['Confirmed_Quantity', 'Confirmed_Value', 'Billing_Quantity', 
                            'Net_Selling_Price', 'Budget_Quantity', 'Budget_Value']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            _DATA_CACHE = df
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to AWS RDS MSSQL Database: {str(e)}")

    return _DATA_CACHE

def execute_sql_on_db(sql_query: str) -> str:
    """Executes the query within an isolated DuckDB connection and intercepts AI hallucinations."""
    
    # --- NEW LOGGING CODE ---
    # Highlights the SQL syntax and prints it in a neat box in the terminal
    syntax = Syntax(sql_query, "sql", theme="monokai", line_numbers=True)
    terminal.print(Panel(syntax, title="🗄️ DATABASE QUERY EXECUTING", border_style="blue", expand=False))
    # ------------------------
    try:
        df = _get_dataframe()
        
        # KEY FIX 1: Use an isolated in-memory connection. 
        # This prevents Streamlit thread issues from dropping the registered table.
        with duckdb.connect(database=':memory:') as conn:
            conn.register('sop_data', df)
            
            # Execute query
            result_df = conn.execute(sql_query).fetchdf()
        
        if result_df.empty:
            return "No data found for this query."
            
        # Return cleanly formatted result for single aggregate values
        if len(result_df) == 1 and len(result_df.columns) == 1:
            val = result_df.iloc[0, 0]
            if isinstance(val, (int, float)):
                return f"{val:,.0f}"
            return str(val)
            
        return result_df.to_string(index=False)
        
    except Exception as e:
        error_msg = str(e)
        
        # KEY FIX 2: Aggressive AI Self-Correction.
        if "does not exist" in error_msg.lower() or "not found" in error_msg.lower():
            return (
                f"SQL Execution Failed: {error_msg}. "
                f"\nCRITICAL INSTRUCTION FOR AI: You are guessing table names. "
                f"The ONLY valid table in this system is named 'sop_data'. "
                f"You MUST immediately rewrite and execute your query using 'FROM sop_data'."
            )
            
        return f"SQL Error: {error_msg}"