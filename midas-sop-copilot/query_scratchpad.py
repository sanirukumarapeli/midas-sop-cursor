import os
import sys
from dotenv import load_dotenv

# Ensure the root directory is in your Python path so imports work cleanly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment configurations
load_dotenv()

try:
    # Import your system's actual data pipelines
    from src.data_query import execute_sql_on_db, _get_dataframe
    
    print("🔄 Initializing system data cache...")
    # Triggering this ensures your local system's cache layer loads exactly like it does in production
    active_cache = _get_dataframe() 
    print(f"✅ Cache initialized successfully. Found {len(active_cache):,} total records.")
    
except Exception as e:
    print(f"❌ Initialization Failed: Could not load the data cache: {str(e)}")
    sys.exit(1)

print("\n=======================================================")
print("🦅 MIDAS S&OP - DUCKDB DIRECT SQL ROUTER INTERACTIVE SHELL")
print("=======================================================")
print("Type your raw SQL queries below and press Enter.")
print("Type 'exit' or 'quit' to close the interactive session.\n")

while True:
    try:
        # Prompt user for entry
        user_sql = input("DuckDB SQL > ").strip()
        
        if not user_sql:
            continue
            
        if user_sql.lower() in ['exit', 'quit']:
            print("Closing debug session. Goodbye!")
            break
            
        # Execute the query straight against the underlying memory structure
        result = execute_sql_on_db(user_sql)
        
        print("\n📊 --- QUERY OUTPUT ---")
        print(result)
        print("-----------------------\n")
        
    except KeyboardInterrupt:
        print("\nClosing debug session. Goodbye!")
        break
    except Exception as err:
        print(f"\n❌ Execution Error: {str(err)}\n")