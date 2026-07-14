import os
import httpx
import urllib3
import datetime
import pandas as pd
import numpy as np
import operator
from typing import Annotated, TypedDict, Sequence, Optional, List, Literal
from dotenv import load_dotenv

# ==========================================
# 🚨 CORPORATE FIREWALL SSL BYPASS FOR TIKTOKEN
# ==========================================
import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Intercept and override the default requests.get to force verify=False
_original_get = requests.get

def _patched_get(*args, **kwargs):
    kwargs['verify'] = False
    return _original_get(*args, **kwargs)

requests.get = _patched_get
# ==========================================

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field # 🚨 NEW IMPORT
import boto3
from langchain_aws import ChatBedrockConverse, BedrockEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from src.forecast import run_demand_inference
from src.optimizer import resolve_production_allocation
from src.risk_analyzer import evaluate_fulfillment_risk
from src.data_query import execute_sql_on_db, _get_dataframe

# ==========================================
# 🚨 NEW TERMINAL LOGGING IMPORTS & CLASS
# ==========================================
import json
from rich.console import Console
from rich.panel import Panel
from langchain_core.callbacks import BaseCallbackHandler

terminal = Console()

class RichTerminalLogger(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        terminal.print("\n[bold cyan]🧠 LLM Routing & Thinking...[/bold cyan]")

    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = serialized.get("name", "Unknown Tool")
        try:
            clean_input = json.dumps(json.loads(input_str), indent=2)
        except:
            clean_input = input_str
        terminal.print(Panel(
            f"[bold yellow]Parameters Passed:[/bold yellow]\n{clean_input}", 
            title=f"🛠️ TOOL TRIGGERED: [bold white]{tool_name}[/bold white]", 
            border_style="yellow",
            expand=False
        ))

    def on_tool_end(self, output, **kwargs):
        preview = str(output)[:300] + ("..." if len(str(output)) > 300 else "")
        terminal.print(f"[bold green]✅ Tool Execution Complete.[/bold green] Output Preview:\n[dim]{preview}[/dim]\n")

    def on_chain_start(self, serialized, inputs, **kwargs):
        terminal.print(f"\n[bold magenta]🚀 New Agent Execution Chain Started[/bold magenta]")
        
# Load environment configuration variables
load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
http_client = httpx.Client(verify=False)

# ==========================================
# 1. SEMANTIC SQL ROUTER MEMORY
# ==========================================
SQL_LIBRARY = [
    # 1. Basic Aggregation & Top Lists
    {"intent": "Find top customers by volume or quantity", "sql": "SELECT Customer, SUM(Confirmed_Quantity) FROM sop_data WHERE LOWER(Regional_Sales_Manager) LIKE '%apac%' GROUP BY Customer ORDER BY SUM(Confirmed_Quantity) DESC LIMIT 5"},
    
    # 2. Financials & Revenue
    {"intent": "Calculate financial budget or revenue totals", "sql": "SELECT SUM(Budget_Value) FROM sop_data WHERE LOWER(Country) = 'germany'"},
    {"intent": "Check average net selling price", "sql": "SELECT AVG(Net_Selling_Price) FROM sop_data WHERE LOWER(Material) LIKE '%glove%'"},
    
    # 3. Operational Risk & Fulfillment
    {"intent": "Find operational fulfillment gaps, backlogs, or delivery risks by plant", "sql": "SELECT Plant, SUM(Confirmed_Quantity) - SUM(Billing_Quantity) AS Fulfillment_Gap FROM sop_data WHERE LOWER(Plant) = 'plant_pk01' GROUP BY Plant"},
    {"intent": "Find customers with the highest unmet demand or shortfall", "sql": "SELECT Customer, SUM(Confirmed_Quantity) - SUM(Billing_Quantity) AS Unmet_Demand FROM sop_data GROUP BY Customer HAVING SUM(Confirmed_Quantity) - SUM(Billing_Quantity) > 0 ORDER BY Unmet_Demand DESC LIMIT 5"},
    
    # 4. Time-Series & Trends (MoM / YoY)
    {"intent": "Find month-over-month sales numbers, timelines, or run-rates", "sql": "SELECT Calendar_Year_Month, SUM(Confirmed_Quantity) FROM sop_data WHERE LOWER(Material_Group_3) LIKE '%palm dipped%' GROUP BY Calendar_Year_Month ORDER BY Calendar_Year_Month ASC"},
    
    # 5. Budget vs. Actual Variance
    {"intent": "Compare actual billed quantity versus budget quantity to find variance", "sql": "SELECT Customer, SUM(Billing_Quantity) AS Actual_Billed, SUM(Budget_Quantity) AS Budget, (SUM(Billing_Quantity) - SUM(Budget_Quantity)) AS Variance FROM sop_data GROUP BY Customer"},
    
    # 6. Product Mix Analysis
    {"intent": "Analyze demand mix by material group or product line", "sql": "SELECT Material_Group_3, SUM(Confirmed_Quantity) FROM sop_data GROUP BY Material_Group_3 ORDER BY SUM(Confirmed_Quantity) DESC"}
]

# 1. Initialize the AWS Boto3 Client for Bedrock
# This automatically picks up your AWS_BEARER_TOKEN_BEDROCK from the .env file
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "ap-southeast-1")
)

# 2. Bypass Embeddings (API Key is exclusively scoped for Nova Lite)
sql_intents = [item["intent"] for item in SQL_LIBRARY]
sql_embeddings = [] 
print("[OK] SYSTEM READY: AWS Bedrock connected (Booting via Nova Lite).")

def get_dynamic_sql_example(user_query: str) -> str:
    """SQL Hints disabled. Nova Lite will rely on its base training to write SQL."""
    return ""

# ==========================================
# 2. TOOL DEFINITIONS
# ==========================================
# ==========================================
# FINAL ANSWER PYDANTIC SCHEMAS (MULTI-PANEL DASHBOARD)
# ==========================================
class ChartDataset(BaseModel):
    name: str
    data: List[float]

class KpiMetric(BaseModel):
    label: str = Field(..., description="Short KPI label, e.g. '2025 total' or 'Peak — Apr'")
    value: str = Field(..., description="Pre-formatted display value, e.g. '$147.0M' or '12.3%'")
    emphasis: Literal["neutral", "positive", "negative"] = Field(
        "neutral",
        description="positive=teal highlight, negative=orange/red highlight, neutral=default white"
    )

class VisualChart(BaseModel):
    chart_type: Literal[
        "line", "bar", "pie", "stacked_bar", "waterfall", "dual_axis",
        "diverging_bar", "horizontal_bar"
    ]
    title: str
    y_axis_unit: Literal["USD", "DPs", "MIXED", "PERCENT"]
    x_axis: List[str]
    datasets: List[ChartDataset]
    show_average_line: bool = Field(
        False,
        description="If true, UI draws a dashed average/reference line on line charts."
    )
    reference_value: Optional[float] = Field(
        None,
        description="Optional explicit reference value (e.g. monthly average). Used when show_average_line is true."
    )

class FinalAnswer(BaseModel):
    """Call this exactly once, as your final step, to deliver the answer to the user. Do not call any other tool after this."""
    response_type: Literal["answer", "clarification"] = Field(
        "answer",
        description=(
            "Use 'clarification' when the user must pick which entity they mean "
            "(set clarification_options). Use 'answer' for normal analytical responses."
        ),
    )
    clarification_options: Optional[List[str]] = Field(
        None,
        description="Exact selectable entity names shown as UI buttons when response_type='clarification'.",
    )
    clarification_field: Optional[str] = Field(
        None,
        description="DB column name when all options share one column (e.g. 'Customer'). Omit for cross-column ambiguity.",
    )
    executive_summary: str = Field(..., description="1-2 concise sentences giving the direct, high-level answer.")
    kpi_metrics: Optional[List[KpiMetric]] = Field(
        None,
        description="3-4 KPI cards for analytical dashboards (total, avg, peak, trough, variance). Omit for simple scalar Q&A."
    )
    visual_charts: Optional[List[VisualChart]] = Field(
        None,
        description="Primary multi-chart array (2-5 charts) for analytical trend/comparison answers. Prefer this over visual_chart."
    )
    visual_chart: Optional[VisualChart] = Field(
        None,
        description="Legacy single chart. Prefer visual_charts. UI will normalize this into a one-item array if visual_charts is empty."
    )
    markdown_table: Optional[str] = Field(None, description="The fetched data strictly formatted as a Markdown table. Omit if not applicable.")
    strategic_insights: Optional[str] = Field(
        None,
        description=(
            "Markdown synthesis of Why/So-What. Use a short intro, then a real numbered list "
            "with each point on its own line (1. ... 2. ... 3. ...), blank line between points. "
            "NEVER cram (1)(2)(3) or (a)(b)(c) into a single paragraph."
        ),
    )
    recommendations: Optional[str] = Field(
        None,
        description=(
            "Markdown with 2-4 actionable directives. Each directive: bold title on its own line "
            "(**Title**), then body text, then blank line. Use bullet sub-points when listing steps. "
            "NEVER dump ALL-CAPS labels and long paragraphs without line breaks."
        ),
    )

@tool(args_schema=FinalAnswer)
def final_answer(**kwargs) -> str:
    """Deliver the final structured answer to the user."""
    return "delivered"


def normalize_final_answer_payload(payload: dict) -> dict:
    """Ensure visual_charts is populated and capped; bridge legacy visual_chart."""
    if not isinstance(payload, dict):
        return payload

    # Clarifications must never carry analytics panels
    if payload.get("response_type") == "clarification":
        payload["visual_charts"] = None
        payload["visual_chart"] = None
        payload["kpi_metrics"] = None
        options = payload.get("clarification_options")
        if isinstance(options, list):
            payload["clarification_options"] = [str(o) for o in options if o is not None and str(o).strip()]
        return payload

    charts = payload.get("visual_charts")
    legacy = payload.get("visual_chart")

    if not charts and legacy:
        charts = [legacy]
    elif isinstance(charts, list) and legacy and len(charts) == 0:
        charts = [legacy]

    if isinstance(charts, list):
        charts = charts[:5]
        payload["visual_charts"] = charts

    kpis = payload.get("kpi_metrics")
    if isinstance(kpis, list):
        payload["kpi_metrics"] = kpis[:4]

    return payload
# ==========================================

# Clarification / exact-resolution is limited to Customer and Plant only.
_ENTITY_DICTIONARY_COLUMNS = [
    "Customer",
    "Plant",
]
_ENTITY_MATCH_CAP = 10


@tool
def check_database_dictionary_tool(search_term: str) -> str:
    """
    CRITICAL ENTITY RESOLUTION TOOL for Customer and Plant names only.
    Call this BEFORE writing SQL or ML filters when the user mentions a company or plant
    (e.g. 'Shelby', 'Work Wear Lanka', 'Plant_PK01').
    Returns STATUS NONE / RESOLVED / AMBIGUOUS with exact DB values. Never invent names.
    Do NOT use this tool to disambiguate Material, Country, or Manager names.
    """
    raw_term = (search_term or "").strip()
    if not raw_term:
        return (
            "STATUS: NONE\n"
            "No search term provided. Ask the user to clarify the entity name."
        )

    clean_term = raw_term.lower()

    try:
        df = _get_dataframe()
        matches_by_col: dict[str, list[str]] = {}

        for col in _ENTITY_DICTIONARY_COLUMNS:
            if col not in df.columns:
                continue
            series = df[col].dropna().astype(str)
            series = series[series.str.strip() != ""]
            hit_mask = series.str.lower().str.contains(clean_term, regex=False, na=False)
            uniques = sorted({v.strip() for v in series[hit_mask].tolist() if v and str(v).strip()})
            if uniques:
                matches_by_col[col] = uniques[:_ENTITY_MATCH_CAP]

        if not matches_by_col:
            return (
                f"STATUS: NONE\n"
                f"No Customer or Plant matches found for '{raw_term}'.\n"
                "AGENT INSTRUCTION: This term is not an ambiguous Customer/Plant. "
                "Continue with normal column mapping (Material, Country, Region, etc.) "
                "without forcing a clarification list."
            )

        columns_hit = list(matches_by_col.keys())
        flat_pairs = [(col, val) for col, vals in matches_by_col.items() for val in vals]
        multi_column = len(columns_hit) > 1
        any_col_multi = any(len(vals) > 1 for vals in matches_by_col.values())

        if len(flat_pairs) == 1 and not multi_column:
            col, val = flat_pairs[0]
            return (
                f"STATUS: RESOLVED\n"
                f"DB_Column: {col}\n"
                f"Exact_Match: {val}\n\n"
                f"AGENT INSTRUCTION: Use exact equality only — "
                f"WHERE LOWER({col}) = LOWER('{val.replace(chr(39), chr(39) + chr(39))}'). "
                f"Do NOT use LIKE '%{raw_term}%' for this entity."
            )

        # AMBIGUOUS: 2+ values in one column and/or hits across multiple columns
        use_cross_column_labels = multi_column
        options: list[str] = []
        for col, vals in matches_by_col.items():
            for val in vals:
                if use_cross_column_labels:
                    options.append(f"{col}: {val}")
                else:
                    options.append(val)

        numbered = "\n".join(f"{i}. {opt}" for i, opt in enumerate(options, start=1))
        field_hint = columns_hit[0] if (not multi_column and any_col_multi) else None

        field_line = f"clarification_field: {field_hint}\n" if field_hint else "clarification_field: null (cross-column)\n"
        options_json = json.dumps(options)

        return (
            f"STATUS: AMBIGUOUS\n"
            f"match_count: {len(options)}\n"
            f"{field_line}"
            f"OPTIONS_JSON: {options_json}\n"
            f"Options:\n{numbered}\n\n"
            "AGENT INSTRUCTION: STOP immediately. Do NOT run analytical SQL or ML tools yet. "
            "Do NOT combine candidates with LIKE. Call `final_answer` once with:\n"
            "  response_type='clarification'\n"
            "  clarification_options = the exact OPTIONS_JSON list above (copy verbatim)\n"
            f"  clarification_field = {json.dumps(field_hint)}\n"
            "  executive_summary = a short question asking which entity the user means\n"
            "  kpi_metrics/visual_charts/strategic_insights/recommendations = omit or null\n"
            "After the user picks an option (button click or typed reply), parse the choice: "
            "if it looks like 'Column: Value', use that column with exact equality on Value; "
            "otherwise use the clarification_field / resolved column. Then continue the ORIGINAL "
            "analytical question from chat history with LOWER(col) = LOWER('exact value')."
        )
    except Exception as e:
        return f"Dictionary scan failed: {str(e)}"

@tool
def forecast_demand_tool(year: int, target_months: list[int], customer_name: str, country_name: str, manager_name: str = "Unknown") -> str:
    """
    Useful to calculate projected demand units using the dual-engine XGBoost model.
    CRITICAL MEMORY RULE: To forecast multiple months (e.g., a full year), pass ALL months inside the `target_months` array (e.g., [1,2,3,4,5,6,7,8,9,10,11,12]).
    MACRO RULE: If predicting global or total company sales, pass 'All' for customer_name.
    """
    results = []
    last_reasoning = ""
    baseline = 0
    
    # Loop through the array to protect memory limits
    for m in target_months:
        res = run_demand_inference(year, m, manager_name, customer_name, country_name)
        
        if isinstance(res, dict) and "forecasted_units" in res:
            units = res["forecasted_units"]
            lower = res.get("confidence_lower", 0)
            upper = res.get("confidence_upper", 0)
            baseline = res.get("historical_baseline", 0)
            last_reasoning = res.get("ai_reasoning", "")
            results.append(f"Month {m}: {units:,.0f} DPs (Worst: {lower:,.0f}, Best: {upper:,.0f})")
        else:
            # 🚨 EXPOSE THE ACTUAL PYTHON ERROR IF IT CRASHES
            err_msg = res.get("error", f"Unknown output format: {res}") if isinstance(res, dict) else str(res)
            results.append(f"Month {m}: FAILED - {err_msg}")

    if len(target_months) == 1:
        return (
            f"The ML engine predicts a baseline demand of {units:,.0f} DPs for {customer_name}. "
            f"The 80% confidence interval projects a worst-case scenario of {lower:,.0f} DPs and a best-case of {upper:,.0f} DPs. "
            f"Historical baseline metric: {baseline:,.0f} DPs. "
            f"AI Reasoning: {last_reasoning}"
        )
    else:
        return (
            f"BATCH FORECAST FOR {year} ('{customer_name}'):\n" + 
            "\n".join(results) + 
            f"\nHistorical baseline metric: {baseline:,.0f} DPs." +
            f"\nAnalysis Basis: {last_reasoning}"
        )

@tool
def check_fulfillment_risk_tool(year: int, month: int, customer_name: str, plant_name: str = "Unknown", nsp: float = 0.0) -> str:
    """Useful to check the mathematical probability of supply chain bottlenecks or shortfalls."""
    risk_data = evaluate_fulfillment_risk(year, month, plant_name, customer_name, nsp)
    
    if isinstance(risk_data, dict) and "probability" in risk_data:
        risk_prob = risk_data["probability"]
        tier = risk_data.get("risk_tier", "Unknown")
        driver = risk_data.get("primary_driver", "Unknown variables")
    else:
        err_msg = risk_data.get('error', 'Unknown Error') if isinstance(risk_data, dict) else 'Invalid Return Format'
        return f"Error: Risk pipeline failed: {err_msg}"

    return (
        f"The calculated operational breach risk at factory {plant_name} for {customer_name} is {risk_prob * 100:.1f}% ({tier} Risk). "
        f"The algorithm identified '{driver}' as the root cause of this risk. "
        f"CRITICAL AGENT INSTRUCTION: You MUST use the `calculate_revenue_at_risk_tool` immediately to find the exact financial Dollar ($) impact of this risk before answering the user."
    )

@tool
def run_supply_optimization_tool(regional_demands: dict) -> str:
    """
    Useful to execute supply routing optimization algorithms to minimize cost parameters.
    CRITICAL: You must pass 'regional_demands' as a dictionary mapping the Region Name to the Demand Volume.
    Example: {"APAC": 150000, "LATAM": 50000, "North America": 200000}
    """
    try:
        df = _get_dataframe()
        
        if df.empty:
            return "ERROR: The S&OP database returned empty. Cannot calculate capacities or route costs."
            
        # 1. Dynamic Live Capacity Calculation
        monthly_plant_vols = df.groupby(['Year', 'Month', 'Plant'])['Confirmed_Quantity'].sum().reset_index()
        max_capacities = monthly_plant_vols.groupby('Plant')['Confirmed_Quantity'].max().to_dict()
        capacities = {plant: float(cap * 1.15) for plant, cap in max_capacities.items()}
        
        # 2. Fully Dynamic Cost Matrix
        df['Clean_Region'] = df['Regional_Sales_Manager'].astype(str).str.strip()
        
        # Calculate specific route averages
        route_sums = df.groupby(['Plant', 'Clean_Region'])[['Confirmed_Value', 'Confirmed_Quantity']].sum().reset_index()
        route_sums['Avg_Unit_Price'] = route_sums['Confirmed_Value'] / route_sums['Confirmed_Quantity'].replace(0, 1)

        # Calculate global plant averages (Failsafe if a plant has never shipped to a requested region)
        plant_sums = df.groupby('Plant')[['Confirmed_Value', 'Confirmed_Quantity']].sum().reset_index()
        plant_sums['Global_Avg_Price'] = plant_sums['Confirmed_Value'] / plant_sums['Confirmed_Quantity'].replace(0, 1)

        cost_matrix = {}
        for plant in capacities.keys():
            cost_matrix[plant] = {}
            
            for region in regional_demands.keys():
                route = route_sums[(route_sums['Plant'] == plant) & (route_sums['Clean_Region'].str.lower() == str(region).lower())]
                
                if not route.empty and route['Avg_Unit_Price'].values[0] > 0:
                    # Use the actual historical price for this specific route
                    unit_price = route['Avg_Unit_Price'].values[0]
                else:
                    # PURE DATA FAILSAFE: Use the factory's global average price instead of a hardcoded number
                    global_plant = plant_sums[plant_sums['Plant'] == plant]
                    unit_price = global_plant['Global_Avg_Price'].values[0] if not global_plant.empty else 0
                
                # Proxy logistics as 12% of the selling price
                cost_matrix[plant][region] = float(unit_price * 0.12) 

        return str(resolve_production_allocation(regional_demands, capacities, cost_matrix))

    except Exception as e:
        # 🚨 THE FIX: NO MORE HARDCODED FALLBACKS.
        # If the DB or math fails, the tool fails gracefully and reports the exact error to the AI.
        return (
            f"SYSTEM ERROR: Supply optimization failed due to calculation or database error: {str(e)}. "
            f"AGENT INSTRUCTION: Do not attempt to guess the answer. Inform the user that the live "
            f"optimization engine cannot be run right now because the live database is unreachable or missing constraints."
        )

@tool
def calculate_revenue_at_risk_tool(year: int, month: int, customer_name: str, plant_name: str, current_nsp: float) -> str:
    """
    EXECUTIVE TOOL: Calculates the exact Dollar ($) Revenue at Risk for a potential fulfillment failure.
    Always use this when executives ask about the financial impact of a supply chain risk.
    """
    # 1. Get the base ML probability of failure
    risk_data = evaluate_fulfillment_risk(year, month, plant_name, customer_name, current_nsp)
    prob = risk_data.get("probability", 0.0)
    
    # 2. Use DuckDB to calculate the exact volume of unfulfilled orders right now
    sql = (f"SELECT SUM(Confirmed_Quantity) - SUM(Billing_Quantity) FROM sop_data "
           f"WHERE LOWER(Customer) = LOWER('{customer_name}') AND LOWER(Plant) = LOWER('{plant_name}') "
           f"AND Calendar_Year = {year} AND Month = {month}")
    
    open_qty_str = execute_sql_on_db(sql)
    
    try:
        # Clean the SQL output and convert to float
        open_qty = float(str(open_qty_str).replace(',', '').strip())
        if open_qty < 0: open_qty = 0.0 # Prevent negative risk if over-billed
    except ValueError:
        open_qty = 0.0
        
    # 3. Calculate Financial Exposure
    max_exposure = open_qty * current_nsp
    expected_loss = max_exposure * prob
    
    return (f"EXECUTIVE FINANCIAL SUMMARY: The maximum revenue exposure (unbilled orders) for {customer_name} at {plant_name} is ${max_exposure:,.2f}. "
            f"Factoring in the ML failure probability of {prob*100:.1f}%, the mathematically Expected Revenue-at-Risk is ${expected_loss:,.2f}. "
            f"AGENT INSTRUCTION: Advise the executive using these specific dollar amounts.")

@tool
def run_vip_triage_tool(region_name: str = "All", limit: int = 5) -> str:
    """
    EXECUTIVE TOOL: Runs a Pareto (ABC) Analysis to identify Tier A (VIP) customers.
    Use this when allocating limited inventory or deciding who gets priority during a shortage.
    The 'limit' parameter controls how many top customers to return (default is 5, but use the user's requested number if provided).
    """
    where_clause = f"WHERE LOWER(Regional_Sales_Manager) LIKE LOWER('%{region_name}%')" if region_name.lower() != "all" else ""
    
    # FIXED: The LIMIT is now dynamic based on the user's prompt, preventing LLM data hallucination
    sql = f"""
    SELECT 
        Customer, 
        SUM(Confirmed_Value) as Total_Revenue
    FROM sop_data 
    {where_clause}
    GROUP BY Customer 
    ORDER BY Total_Revenue DESC 
    LIMIT {limit}
    """
    result = execute_sql_on_db(sql)
    return (f"VIP TRIAGE RESULTS (Top {limit} EBITDA Contributors in {region_name}): \n{result}\n"
            f"AGENT INSTRUCTION: These are Tier A accounts. Advise the executive to prioritize allocating "
            f"inventory to these specific accounts during capacity constraints to protect company margins.")

@tool
def forecast_budget_pacing_tool(target_year: int, manager_name: str) -> str:
    """
    EXECUTIVE TOOL: Calculates if a sales manager or region is mathematically pacing to hit their Annual Budget.
    """
    # FIXED: The WHERE clause now securely checks BOTH manager columns to ensure human names are always found
    sql = f"""
    SELECT 
        SUM(Confirmed_Value) as Actual_Revenue_YTD,
        SUM(Budget_Value) as Annual_Budget_Target,
        (SUM(Confirmed_Value) / NULLIF(SUM(Budget_Value), 0)) * 100 as Attainment_Percentage
    FROM sop_data
    WHERE Calendar_Year = {target_year} 
    AND (LOWER(Regional_Sales_Manager) LIKE LOWER('%{manager_name}%') 
         OR LOWER(Key_Account_Manager) LIKE LOWER('%{manager_name}%'))
    """
    result = execute_sql_on_db(sql)
    return (f"BUDGET PACING ANALYSIS for {manager_name} in {target_year}: \n{result}\n"
            f"AGENT INSTRUCTION: Analyze this attainment percentage. If it is below 100%, explicitly state the dollar gap "
            f"(Budget minus Actuals) and warn the executive that immediate intervention is required.")

@tool
def query_historical_data_tool(sql_query: str) -> str:
    """
    Executes a SQL query against the S&OP database.
    
    CRITICAL SCHEMA & DATA MAPPING RULES (NEVER VIOLATE THESE):
    1. THE TABLE: ALWAYS use 'FROM sop_data'. Never invent table names.
    
    2. THE UNIVERSAL ENTITY DICTIONARY (CRITICAL):
       When a user asks to filter the data, categorize their word and map it to the exact columns below:
       
       - COMPANIES / CLIENTS (e.g., '3M', 'Honeywell', 'Grainger'): 
         -> Search ONLY in 'Customer'.
         
       - GEOGRAPHY & REGIONS (e.g., 'APAC', 'North America', 'USA', 'Germany'): 
         -> If it is a broad Region: Search in 'Regional_Sales_Manager' or 'Sales_Organization'. (NOTE: 'Regional_Sales_Manager' holds regions, NOT human names).
         -> If it is a specific Nation: Search ONLY in 'Country'.
         
       - HUMAN PERSONNEL (e.g., 'Rahul Sharma', 'Carlos', 'Elena'): 
         -> Search in 'Key_Account_Manager', 'Vice_President', or 'AAM'.
         
       - SUPPLY CHAIN / FACTORIES (e.g., 'Plant_PK01', 'LK01', 'Factory'): 
         -> Search ONLY in 'Plant'.
         -> ACRONYM TRANSLATION: You MUST universally translate the following acronyms into their exact official database values before writing SQL:
            * 'MSC' -> 'MIDAS SAFETY CEYLON (PVT) LTD'
            * 'BEL' -> 'Beltexco'
            * 'PSL' -> 'Prime Safety Limited'
         
       - PRODUCTS & MATERIALS (e.g., 'Supported', 'Gloves', 'Mechanic', 'CM-81989'): 
         -> Because product names vary, you MUST use an OR statement across the product hierarchy: 
         (LOWER(Product) LIKE '%term%' OR LOWER(Material_Group_1_MST) LIKE '%term%' OR LOWER(Material) LIKE '%term%')

       - MATERIAL GROUP ABBREVIATIONS (e.g., 'MG1', 'MG2', 'MG3', 'MG4', 'MG5'):
         -> You MUST dynamically translate any 'MG' abbreviation directly into the corresponding database column (e.g., 'MG1' becomes 'Material_Group_1_MST', 'MG2' becomes 'Material_Group_2_MST', etc.). Apply this translation to both SELECT clauses and WHERE filters.
         
       - NEW BUSINESS FLAGS (e.g., 'New Customer', 'New Product'):
         -> Filter using 'New_Bus_Customer_Indicator' = 'Y' or 'New_Bus_Material_Indicator' = 'Y'.
    
    3. DATES & TIME:
       - 'Calendar_Year' is a 4-digit integer (e.g., 2025, 2026).
       - 'Calendar_Year_Month' is a 6-digit format (e.g., '202501' for January 2025).
       - DEFAULT TIMEFRAME: If the user does not specify a year, you MUST append 'WHERE Calendar_Year = [Current Anchor Year]'.
    
    4. METRICS, AGGREGATION & SEMANTIC MAPPING:
       - THE "SUM" DEFAULT RULE: Default to SUM() for ALL numerical metrics (Confirmed_Value, Confirmed_Quantity, etc.). 
       - DYNAMIC UNIT SWITCHING (CRITICAL): Before generating SQL, identify the unit (USD vs DPs).
         * If User asks for "USD" / "Revenue" / "Sales" -> You MUST use 'Confirmed_Value'.
         * If User asks for "DPs" / "Volume" / "Quantity" -> You MUST use 'Confirmed_Quantity'.
         * NEVER reuse a previous query structure without verifying the unit column. If the unit changes, the column MUST change.
       - STRICT METRIC MAPPING: 
         * "net selling value" / "price" / "margin" -> 'Net_Selling_Price'
         * "confirmed value" / "revenue" / "sales" / "ebitda" -> 'Confirmed_Value'
         * "volume" / "quantity" / "DPs" -> 'Confirmed_Quantity'
         * "budget" / "target" -> 'Budget_Value' or 'Budget_Quantity'
    
    5. BULLETPROOF FILTERING (ENTITY RESOLUTION):
       - RESOLVED / user-selected exact entity (from check_database_dictionary_tool or a clarification pick):
         use exact equality — WHERE LOWER(Customer) = LOWER('Shelby Group International, Inc').
       - Explicit "all matching" / combined partial request from the user:
         LIKE is allowed — WHERE LOWER(Customer) LIKE '%shelby%'.
       - Unresolved AMBIGUOUS entities: do NOT query; clarify first via final_answer clarification.
       - If the filter looks like a Customer or Plant name and may be ambiguous, run check_database_dictionary_tool first.
       
    6. THE INVESTIGATIVE PROTOCOL:
       - If a user asks for a high-level metric, proactively execute secondary queries (like GROUP BY Calendar_Year_Month) to find contextual run-rate trends before answering.
    """
    raw_result = execute_sql_on_db(sql_query)
    
    # --- FIXED & BULLETPROOFED: GENERIC AUTO-CORRECTION UPGRADE ---
    empty_flags = ["no data found", "empty dataframe", "0 rows", "nan", "none"]
    raw_lower = str(raw_result).strip().lower()
    
    if not raw_lower or raw_lower == "" or any(flag in raw_lower for flag in empty_flags):
        try:
            df = _get_dataframe()
            search_terms = [word.strip("' %").lower() for word in sql_query.split() if "%" in word or "'" in word]
            
            suggestions = []
            if search_terms:
                target = search_terms[0]
                text_columns = df.select_dtypes(include=['object', 'string']).columns
                
                for col in text_columns:
                    unique_vals = df[col].dropna().unique()
                    matches = [str(v) for v in unique_vals if target in str(v).lower()]
                    if matches:
                        suggestions.append(f"In column '{col}', close actual records include: {matches[:3]}")
            
            suggestion_text = " | ".join(suggestions)
            return (
                f"ATTENTION AGENT: Your SQL query executed successfully but returned 0 active rows (Output was: {raw_result}). "
                f"This means your filter values do not strictly exist in the database. "
                f"DATABASE PROFILE HINT: {suggestion_text if suggestions else 'No partial matches found. Check column spellings.'}. "
                f"Please fix your WHERE clause using these verified terms and run the query again."
            )
        except Exception:
            pass
            
    return raw_result

# ==========================================
# 3. LANGGRAPH ENTERPRISE STATE MACHINE
# ==========================================
# Graph state architecture to track messages seamlessly without brittle loops
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

class MidasCustomAgentExecutor:
    """A direct execution harness powered by LangGraph state machine routing."""
    def __init__(self, llm, tools, data_anchor_date: str):
        self.llm_with_tools = llm.bind_tools(tools)
        self.data_anchor_date = data_anchor_date
        
        # Construct the cyclical graph topology
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self.call_agent)
        workflow.add_node("tools", ToolNode(tools))
        
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", self.should_continue, {"continue": "tools", "end": END})
        workflow.add_edge("tools", "agent")
        
        self.app = workflow.compile()

    def call_agent(self, state: AgentState):
        messages = state['messages']
        
        # Intercept the latest input to execute semantic hinting
        latest_human_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        dynamic_sql_hint = get_dynamic_sql_example(latest_human_msg)
        
        # 🚨 THE FIX: Extract the year from the anchor date before the prompt uses it
        
        current_anchor_year = self.data_anchor_date.split()[-1]
        system_message = SystemMessage(content=(
            f"You are the elite Midas Safety S&OP AI Co-Pilot, operating as a top-tier executive strategic advisor.\n"
            f"CRITICAL TIME ANCHOR: Your historical dataset ends in {self.data_anchor_date}. "
            f"The current operational year is {current_anchor_year}. Whenever a user asks for 'next month' or relative timeframes, calculate it relative to this anchor.\n"
            "Your mission is to help directors evaluate demand, supply risks, and raw datasets.\n\n"
            
            "--- CORE OPERATING PRINCIPLES ---\n"
            "1. ABSOLUTE TRUTH: Always use your DuckDB historical query tool to pull exact numbers. NEVER guess. Your only data source is the 'sop_data' table.\n"
            "2. LOOK BEFORE YOU LEAP (DATA DISCOVERY): If the user mentions a Customer or Plant name (e.g., 'Work Wear Lanka', 'Shelby', 'Plant_PK01'), you MUST use the `check_database_dictionary_tool` FIRST before writing SQL or calling ML tools. This tool ONLY resolves Customer and Plant — not Material, Country, or Manager.\n"
            "2b. ENTITY DISAMBIGUATION (CRITICAL — Customer & Plant only): After `check_database_dictionary_tool`:\n"
            "   - STATUS AMBIGUOUS: STOP. Immediately call `final_answer` with response_type='clarification', copy clarification_options from OPTIONS_JSON verbatim, set clarification_field when provided, and put a short clarifying question in executive_summary. Leave kpi_metrics/visual_charts/strategic_insights/recommendations null. Do NOT run analytical SQL. Do NOT merge candidates with LIKE '%term%'. Do NOT invent Material/Country options in the clarification list.\n"
            "   - STATUS RESOLVED: Filter with exact equality LOWER(col) = LOWER('exact value') only.\n"
            "   - STATUS NONE: The term is not a known Customer/Plant match — continue with normal column mapping (Material/Country/Region as appropriate) without forcing a clarification.\n"
            "   - After the user selects an option (UI button or typed name), continue the ORIGINAL analytical question from chat history using exact equality on that choice. LIKE merges are only allowed if the user explicitly asks for all matching entities.\n"
            "3. FINAL STEP RULE: Once you have gathered all data needed to answer (or when issuing a clarification), call the `final_answer` tool exactly once with your complete response. Never write your final answer as plain text.\n"
            "4. NO BOILERPLATE: Never use robotic phrases like 'Here is the data you requested'. Speak with executive authority.\n"
            "5. PROACTIVE INVESTIGATION (CRITICAL): If the user asks for a high-level aggregate (e.g., 'Total sales by region'), DO NOT just query the annual totals. You MUST proactively use your DuckDB tool to query the MONTHLY breakdown (GROUP BY Calendar_Year_Month) alongside the totals so you can generate a rich 'line' chart and provide deep insights on seasonality and trends.\n"
            f"6. TIMEFRAME AWARENESS: Your historical DuckDB data strictly ends in {current_anchor_year}, and you MUST default to filtering SQL queries by this year unless asked otherwise. HOWEVER, your Machine Learning tools (Demand & Risk) are explicitly designed to predict the FUTURE. You are fully authorized and expected to run forecasts for 2027, 2028, and beyond.\n"
            "7. NO HALLUCINATIONS: If your SQL tool returns an error message, do NOT output '0'. Rewrite the SQL query correctly and try again.\n"
            "8. FORMATTING TERMINOLOGY & READABILITY (CRITICAL):\n"
            "   - NUMBERS: VOLUME MUST use 'DPs'. CURRENCY MUST use USD with the '$' symbol. Format all numbers >999 with commas (e.g., '13,020,605.30').\n"
            "   - TABLE HEADERS: NEVER use raw database column names with underscores in your markdown tables. Convert them to clean, human-readable titles (e.g., 'Calendar_Year_Month' MUST become 'Month', 'Total_Sales' MUST become 'Total Sales').\n"
            "   - DATES: You MUST translate raw 'YYYYMM' database formats into readable text (e.g., convert '202501' to 'January 2025') inside your tables and text.\n"
            "   - LIST SPACING (CRITICAL — strategic_insights AND recommendations):\n"
            "     * Use proper Markdown lists. Each numbered/bulleted point MUST be on its own line.\n"
            "     * Separate every list item with a blank line (\\n\\n) for UI readability.\n"
            "     * FORBIDDEN: cramming inline markers like (1) (2) (3) or (a) (b) (c) into one dense paragraph.\n"
            "     * strategic_insights example:\\n"
            "       The year shows three phases:\\n\\n"
            "       1. Strong Q1 performance driven by ...\\n\\n"
            "       2. Mid-year volatility as ...\\n\\n"
            "       3. Q4 collapse tied to ...\\n\\n"
            "     * recommendations example:\\n"
            "       **Immediate Escalation**\\n\\n"
            "       Contact the account team to ...\\n\\n"
            "       **Product Diversification**\\n\\n"
            "       Hedge concentration risk by ...\\n\\n"
            "\n"
            "9. THE DUAL-ENGINE AI LAW (CRITICAL): Your ML tools (`forecast_demand_tool`) are fully equipped with a dual-engine architecture. For MICRO-level requests (specific customers), pass their exact names. For MACRO-level requests (e.g., 'Total company sales by month in 2027'), you MUST use the ML tool and pass 'All' into the customer parameter. The backend will automatically route your request to the Top-Down Macro AI Model. DO NOT use SQL to forecast future demand.\n"
            "10. COMPLEX MATH & MACRO FORECASTING (UNIVERSAL RULE): The ML model is strictly for specific customer/country predictions. For ALL macro-level tasks (global forecasts, annual projections, quarterly variance, etc.):\n"
            "    A) Pull the required historical groupings using the DuckDB SQL tool.\n"
            "    B) DO NOT guess or silently average numbers.\n"
            "    C) You MUST use 'Chain of Thought' mathematics. Explicitly state the mathematical methodology you are choosing.\n\n"
            
            "--- MULTI-PANEL DASHBOARD PROTOCOL (CRITICAL) ---\n"
            "11. DASHBOARD RULES: For analytical queries (MoM/YoY trends, budget vs actual, regional or product mix, customer trajectories over months), "
            "you MUST return a multi-panel dashboard — NOT a single chart.\n"
            "   A) kpi_metrics: Emit 3–4 KPI cards derived from the data (e.g. year total, monthly avg, peak month, trough month, or variance %). "
            "Use emphasis='positive' for peaks/growth and 'negative' for troughs/declines. Pre-format values as strings ($147.0M, 12.3%, 1.2M DPs).\n"
            "   B) visual_charts: Emit 2–4 coordinated charts in this array (cap at 5). Prefer visual_charts over the legacy visual_chart field.\n"
            "      Typical pack for an entity+year trajectory:\n"
            "      - line: monthly actual vs budget and/or prior year (set show_average_line=true and reference_value to monthly avg when useful)\n"
            "      - diverging_bar: month-on-month % change (y_axis_unit='PERCENT')\n"
            "      - stacked_bar: regional or product contribution by month\n"
            "      - pie: product/region mix share\n"
            "      - horizontal_bar: ranked YoY growth by month or top entities\n"
            "   C) Simple scalar Q&A (single total with no comparative series): omit kpi_metrics and visual_charts (leave null). Do NOT force a 5-chart dashboard.\n"
            "   C2) Clarification responses (response_type='clarification'): NEVER attach charts, KPIs, or tables. Only executive_summary + clarification_options.\n"
            "   D) INVESTIGATION REQUIREMENT: For entity + year style questions, fetch (1) monthly series, (2) MoM or YoY when a comparable year exists, "
            "and (3) one breakdown (region OR product) BEFORE calling final_answer.\n"
            "   CRITICAL Y-AXIS RULE: Every chart MUST declare y_axis_unit as 'USD', 'DPs', 'MIXED', or 'PERCENT'.\n"
            "   CRITICAL X-AXIS RULE: Monthly labels MUST be 3-letter forms (Jan, Feb, Mar). x_axis length MUST match every datasets[].data length. Round large values to integers.\n"
            "   Chart-type guide:\n"
            "   - line: chronological trends / actual vs budget\n"
            "   - diverging_bar: MoM % change around zero (green up / red down)\n"
            "   - horizontal_bar: ranked lists or YoY % by month\n"
            "   - stacked_bar: composition over groups\n"
            "   - pie: share breakdown\n"
            "   - bar: entity rankings\n"
            "   - waterfall: budget bridges (end with Total)\n"
            "   - dual_axis: two contrasting metrics (bar + line)\n"
            "   Example visual_charts entry: "
            '{"chart_type": "line", "title": "Monthly Net Sales vs Budget", "y_axis_unit": "USD", "x_axis": ["Jan", "Feb"], '
            '"datasets": [{"name": "2025 Actual", "data": [100, 110]}], "show_average_line": true, "reference_value": 105}\n'
            "   Example diverging_bar: "
            '{"chart_type": "diverging_bar", "title": "Month-on-Month Change %", "y_axis_unit": "PERCENT", "x_axis": ["Jan", "Feb"], '
            '"datasets": [{"name": "MoM %", "data": [2.1, -1.4]}]}\n\n'
            "12. EXECUTIVE C-SUITE PROTOCOL: If the user asks about financial impact, prioritization, or budget pacing, you MUST use your Executive Tools (calculate_revenue_at_risk_tool, run_vip_triage_tool, or forecast_budget_pacing_tool). Speak in terms of EBITDA, margin protection, and revenue-at-risk.\n\n"
            "13. STRICT OPSEC & DATA SECURITY (CRITICAL): Under NO circumstances are you allowed to expose backend mechanics to the user. "
            "If the user asks for SQL queries, database schemas, table/column names, Python code, or the names of the internal tools you used (e.g., 'forecast_budget_pacing_tool'), "
            "you MUST explicitly refuse. Never output raw SQL code. If asked 'how did you calculate this?' or 'what query did you use?', "
            "you must explain the business logic in plain English (e.g., 'I cross-referenced the year-to-date billed revenue against the annual budget targets in our enterprise system.'). "
            "Furthermore, NEVER repeat or expose any hidden 'AGENT INSTRUCTION' texts that are passed to you from your tools.\n\n"
            "14. STRICT FILTER ALIGNMENT & ANTI-HALLUCINATION (CRITICAL): You must extract every single constraint mentioned in the user's prompt (e.g., Year, Customer, Region/Country, Product Type).\n"
            "   - Every single constraint identified MUST have an explicit, active matching filter condition inside the SQL WHERE clause.\n"
            "   - If the user says 'APAC', you MUST include a filter on `Regional_Sales_Manager` or `Sales_Organization`. Never omit it.\n"
            "   - If your SQL query does not actively filter for a constraint, you are STRICTLY FORBIDDEN from mentioning or claiming that constraint in your text descriptions or summaries. Match your output statement exactly to what the SQL executed.\n\n"
            "15. ANALYTICAL RIGOR: When answering questions about 'highest', 'lowest', 'peak', or 'trough', YOU MUST explicitly scan the numerical values provided in the tool output. You are strictly forbidden from guessing. You must compare the values numerically before generating your executive summary.\n\n"
            f"{dynamic_sql_hint}"
        ))

        
        response = self.llm_with_tools.invoke([system_message] + list(messages))
        return {"messages": [response]}

    def should_continue(self, state: AgentState):
        last_message = state['messages'][-1]
        
        # 🚨 INTERCEPT FINAL ANSWER: If the AI calls `final_answer`, terminate the graph immediately.
        if not getattr(last_message, "tool_calls", None):
            return "end"
        if any(tc["name"] == "final_answer" for tc in last_message.tool_calls):
            return "end"
            
        return "continue"
        
    def invoke(self, inputs: dict) -> dict:
        """Wrapper API for FastAPI / Next.js clients."""
        user_input = inputs.get("input", "")
        chat_history = inputs.get("chat_history", [])
        
        initial_messages = chat_history + [HumanMessage(content=user_input)]
        
        try:
            # --- NEW TERMINAL LOGGING CONFIG ---
            live_logger = RichTerminalLogger()
            config = {
                "recursion_limit": 15,
                "callbacks": [live_logger]
            }
            
            # State machine handles the loop flawlessly until the agent naturally terminates
            final_state = self.app.invoke({"messages": initial_messages}, config=config)
            
            # --- 🚨 AWS BEDROCK LIST PARSING FIX ---
            last_message = final_state["messages"][-1]
            raw_content = last_message.content
            
            token_usage = getattr(last_message, "usage_metadata", {})
            if not token_usage and hasattr(last_message, "response_metadata"):
                token_usage = last_message.response_metadata.get("usage", {})
            
            # 🚨 THE FIX (Step 4 Extraction): Pull the structured payload directly from the tool args.
            final_call = next(
                (tc for tc in getattr(last_message, "tool_calls", []) if tc["name"] == "final_answer"),
                None
            )

            if final_call:
                output_payload = normalize_final_answer_payload(dict(final_call["args"]))
            else:
                # Fallback in the rare event it ignores instructions and writes raw text
                raw_content = last_message.content
                if isinstance(raw_content, list):
                    parsed_text = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block) 
                        for block in raw_content
                    )
                else:
                    parsed_text = str(raw_content)
                output_payload = {"executive_summary": parsed_text}
            
            return {
                "output": output_payload, # Returns dictionary now
                "usage": token_usage
            }
        except Exception as e:
            error_msg = str(e).lower()
            if "recursion limit" in error_msg:
                return {
                    "output": "⚠️ **System Override:** The request was too broad, causing the AI to analyze too many simultaneous scenarios.\n\n"
                              "To prevent system timeouts, please narrow your request. For predictive analytics, specify a **Year, Month, Customer, and Plant** (e.g., *'What is the risk for 3M in Plant_PK01 for Jan 2026?'*). If you want a macro-level view, ask to summarize historical S&OP trends instead."
                }
            return {"output": f"⚠️ **System Error:** The processing engine encountered an unexpected hurdle: `{str(e)}`"}


def dynamically_fetch_latest_date() -> str:
    """Scans the DB to find the most recent date. Falls back to the real-world system clock if the DB drops."""
    try:
        df = _get_dataframe()
        
        # If the DB is empty or missing the column, fallback to today's real-world date
        if 'Calendar_Year_Month' not in df.columns or df.empty:
            return datetime.date.today().strftime("%B %Y")
            
        max_ym = str(df['Calendar_Year_Month'].max())
        year = int(max_ym[:4])
        month = int(max_ym[4:6])
        latest_date = datetime.date(year, month, 1)
        
        return latest_date.strftime("%B %Y")
        
    except Exception as e:
        print(f"Time Anchor Warning: {e}. Defaulting to live system clock.")
        # Dynamic Fallback: Uses the actual server/laptop current date
        return datetime.date.today().strftime("%B %Y")


def get_integrated_copilot_agent():
    # Initialize the Anthropic Claude Sonnet 4.6 model via Bedrock Converse API
    llm = ChatBedrockConverse(
        client=bedrock_client, 
        model_id="arn:aws:bedrock:ap-southeast-1:945604190587:inference-profile/global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        provider="anthropic", 
        temperature=0
    )
    
    tools = [
        forecast_demand_tool, 
        check_fulfillment_risk_tool, 
        run_supply_optimization_tool, 
        query_historical_data_tool,
        calculate_revenue_at_risk_tool,
        run_vip_triage_tool,
        forecast_budget_pacing_tool,
        check_database_dictionary_tool,
        final_answer
    ]
    
    latest_date_str = dynamically_fetch_latest_date()
    
    return MidasCustomAgentExecutor(llm, tools, latest_date_str)
