# location: app.py
import streamlit as st
import re
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.callbacks import get_openai_callback
from src.chat_agent import get_integrated_copilot_agent

# ==========================================
# 1. PAGE LAYOUT & CONTROL TOWERS CONFIG
# ==========================================
st.set_page_config(
    page_title="Midas S&OP AI Co-Pilot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium Sidebar Operations HUD
with st.sidebar:
    st.markdown("### 🏭 S&OP Control Tower")
    st.markdown("---")
    st.subheader("System Status")
    
    st.success("⚡ Intelligent S&OP Co-Pilot: Active")
    st.success("📈 Demand Forecasting Module: Live")
    st.success("🛡️ Fulfillment Reliability Engine: Operational")
    st.success("⚙️ Network Optimization Engine: Linked")
    
    st.markdown("---")
    st.markdown("""
    **Quick Capabilities Guide:**
    - Request dynamic demand horizon trends.
    - Check operational variance bottlenecks.
    - Resolve cost-minimizing shipment matrices.
    - Ask for monthly trends to generate charts!
    """)
    st.markdown("---")
    
    if st.button("🔄 Reset Copilot Analytics"):
        st.session_state.chat_history = []
        st.session_state.last_metrics = (None, None)
        st.rerun()
        
    # --- NEW: LIVE DB RETRAINING BUTTON ---
    st.markdown("---")
    st.markdown("### 🧠 ML Admin Controls")
    if st.button("🚀 Retrain Models (Live DB)"):
        with st.spinner("Pulling live MSSQL data and retraining XGBoost models... This may take a minute."):
            try:
                import src.data_query
                from src.train import train_and_serialize_models
                
                # 1. Clear the cache to force a fresh pull from the live database
                src.data_query._DATA_CACHE = None 
                
                # 2. Trigger the training pipeline
                train_and_serialize_models()
                
                st.success("✅ Models retrained successfully on live database!")
            except Exception as e:
                st.error(f"Model Retraining Failed: {str(e)}")

st.title("🤖 Midas Safety S&OP AI Co-Pilot")
st.caption("Enterprise-Grade Supply Chain Predictive Analytics & Linear Programming Decision Suite")

# ==========================================
# 2. STATE PERSISTENCE INITIALIZATION
# ==========================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = (None, None)

@st.cache_resource
def load_cached_sop_agent():
    return get_integrated_copilot_agent()

try:
    agent_harness = load_cached_sop_agent()
except Exception as e:
    st.error(f"Fatal compilation roadblock on S&OP Agent Engine initialization: {str(e)}")
    st.stop()


def parse_sop_metrics(response_text: str):
    """Extracts high-level KPIs for the top tiles."""
    demand_val = None
    risk_val = None
    
    demand_match = re.search(r'([\d,]+)\s*(?:DPs|units)', response_text, re.IGNORECASE)
    if demand_match:
        demand_val = f"{demand_match.group(1)} DPs"
        
    risk_match = re.search(r'([\d.]+%)', response_text)
    if risk_match:
        risk_val = risk_match.group(1)
        
    return demand_val, risk_val


def extract_and_render_visuals(text_response: str, key: str = None):
    """Scans LLM text for JSON blocks, renders advanced Plotly chart elements, and cleans output text."""
    # 1. Try finding backtick-wrapped JSON first
    json_matches = list(re.finditer(r'```json\s*(.*?)\s*```', text_response, re.DOTALL | re.IGNORECASE))
    
    # FALLBACK ENGINE: If the LLM forgot code-block backticks, search for raw curly-brace JSON objects
    if not json_matches:
        json_matches = list(re.finditer(r'(\{\s*"chart_type"\s*:.*?\s*\})', text_response, re.DOTALL | re.IGNORECASE))
    
    clean_text = text_response
    chart_data = None
    
    if json_matches:
        # 2. Strip ALL detected JSON strings out of the raw text response
        for match in json_matches:
            clean_text = clean_text.replace(match.group(0), "")
            
        # 3. Parse the FIRST structurally valid segment
        for match in json_matches:
            try:
                # If it matched the fallback regex, group(1) contains the raw braces directly
                json_str = match.group(1).strip()
                chart_data = json.loads(json_str)
                break 
            except json.JSONDecodeError:
                continue
                
    # 4. Print the clean textual analysis narrative
    st.markdown(clean_text.strip())
    
    # 5. Render the Chart if we found valid data
    if chart_data:
        try:
            chart_type = str(chart_data.get("chart_type", "line")).lower()
            chart_title = chart_data.get("title", "S&OP Metric Visualization Profile")
            x_labels = chart_data.get("x_axis", [])
            datasets = chart_data.get("datasets", [])
            
            if not datasets or not x_labels:
                return clean_text
                
            st.markdown(f"### 📈 {chart_title}")
            
            if chart_type == "dual_axis":
                fig = make_subplots(specs=[[{"secondary_y": True}]])
            else:
                fig = go.Figure()

            if chart_type == "line":
                for series in datasets:
                    fig.add_trace(go.Scatter(x=x_labels, y=series.get("data", []), mode='lines+markers', name=series.get("name", "")))
            
            elif chart_type == "bar":
                for series in datasets:
                    fig.add_trace(go.Bar(x=x_labels, y=series.get("data", []), name=series.get("name", "")))
                fig.update_layout(barmode='group')
                
            elif chart_type == "stacked_bar":
                for series in datasets:
                    fig.add_trace(go.Bar(x=x_labels, y=series.get("data", []), name=series.get("name", "")))
                fig.update_layout(barmode='stack')
                
            elif chart_type == "pie":
                series = datasets[0]
                fig.add_trace(go.Pie(labels=x_labels, values=series.get("data", []), name=series.get("name", ""), hole=0.4))
                
            elif chart_type == "waterfall":
                series = datasets[0]
                y_data = series.get("data", [])
                measures = ["total" if "total" in str(x).lower() else "relative" for x in x_labels]
                if "total" not in [m.lower() for m in measures] and len(measures) > 1:
                    measures[-1] = "total"
                    
                fig.add_trace(go.Waterfall(
                    x=x_labels, y=y_data, measure=measures, name=series.get("name", ""),
                    connector={"line": {"color": "rgba(255,255,255,0.3)"}},
                    increasing={"marker": {"color": "#2ca02c"}},
                    decreasing={"marker": {"color": "#d62728"}},
                    totals={"marker": {"color": "#1f77b4"}}
                ))
                
            elif chart_type == "dual_axis":
                if len(datasets) > 0:
                    fig.add_trace(go.Bar(x=x_labels, y=datasets[0].get("data", []), name=datasets[0].get("name", ""), opacity=0.7), secondary_y=False)
                if len(datasets) > 1:
                    fig.add_trace(go.Scatter(x=x_labels, y=datasets[1].get("data", []), mode='lines+markers', name=datasets[1].get("name", ""), line=dict(color="#ff7f0e", width=3)), secondary_y=True)

            else:
                for series in datasets:
                    fig.add_trace(go.Scatter(x=x_labels, y=series.get("data", []), mode='lines+markers', name=series.get("name", "")))

            fig.update_layout(
                template="plotly_dark", 
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True, key=key)
            
        except Exception as e:
            st.error(f"Failed to render advanced visualization payload: {e}")
            
    return clean_text

# ==========================================
# 3. LIVE METRIC CALLOUT TILES
# ==========================================
cached_demand, cached_risk = st.session_state.last_metrics

if cached_demand or cached_risk:
    st.markdown("### 📊 Active Pipeline Signals")
    col1, col2 = st.columns(2)
    with col1:
        if cached_demand:
            st.metric(label="Target Market Volume Profile", value=cached_demand)
        else:
            st.metric(label="Target Market Volume Profile", value="--")
    with col2:
        if cached_risk:
            color_state = "normal" if cached_risk == "0.0%" else "inverse"
            st.metric(
                label="Operational Fulfillment Variance Risk", 
                value=cached_risk, 
                delta="Stable Fleet" if cached_risk == "0.0%" else "Action Required",
                delta_color=color_state
            )
        else:
            st.metric(label="Operational Fulfillment Variance Risk", value="--")
    st.markdown("---")


# ==========================================
# 4. CHAT BUBBLE CONTEXT CONTAINERS
# ==========================================
for idx, message in enumerate(st.session_state.chat_history):
    if isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.markdown(message.content)
    elif isinstance(message, AIMessage):
        with st.chat_message("assistant", avatar="🤖"):
            # Pass a unique key based on the position in history
            extract_and_render_visuals(message.content, key=f"chart_hist_{idx}")
            if "tokens" in message.additional_kwargs:
                st.markdown(message.additional_kwargs["tokens"])

# ==========================================
# 5. INPUT TRAFFIC ACTION CONTROLLER
# ==========================================
if user_prompt := st.chat_input("Enter S&OP metrics request, allocation targets, or scenario queries..."):
    
    st.session_state.chat_history.append(HumanMessage(content=user_prompt))
    
    with st.chat_message("user"):
        st.markdown(user_prompt)
    
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Processing scenario calculations across multi-horizon neural nodes..."):
            try:
                # --- NEW: Sliding Window Memory Buffer ---
                # We cap the history at the last 10 messages (5 conversational turns)
                MAX_HISTORY_LENGTH = 10
                current_history = st.session_state.chat_history[:-1]
                
                if len(current_history) > MAX_HISTORY_LENGTH:
                    pruned_history = current_history[-MAX_HISTORY_LENGTH:]
                else:
                    pruned_history = current_history

                with get_openai_callback() as cb:
                    agent_response = agent_harness.invoke({
                        "input": user_prompt,
                        # Pass the pruned history instead of the entire infinite array
                        "chat_history": pruned_history 
                    })
                
                final_answer = agent_response.get("output", "Empty traffic stream returned.")
                clean_answer = extract_and_render_visuals(final_answer, key=f"chart_live_{len(st.session_state.chat_history)}")
                
                token_footnote = f"\n\n---\n*📊 Tokens Used — Input: {cb.prompt_tokens:,} | Output: {cb.completion_tokens:,} | Total: {cb.total_tokens:,}*"
                
                st.session_state.chat_history.append(AIMessage(
                    content=final_answer,
                    additional_kwargs={"tokens": token_footnote}
                ))
                
                fresh_demand, fresh_risk = parse_sop_metrics(final_answer)
                if fresh_demand or fresh_risk:
                    st.session_state.last_metrics = (
                        fresh_demand if fresh_demand else cached_demand, 
                        fresh_risk if fresh_risk else cached_risk
                    )
                
                st.rerun()
                    
            except Exception as e:
                st.error(f"Execution engine failure encountered within loop container: `{str(e)}`")