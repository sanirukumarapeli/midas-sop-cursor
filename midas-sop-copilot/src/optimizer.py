# location: src/optimizer.py
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, value

def resolve_production_allocation(demands, capacities, cost_matrix, high_risk_regions=None):
    """Solves multi-facility resource distribution with AI Safety Stock Buffering."""
    prob = LpProblem("Midas_SOP_Optimizer", LpMinimize)
    
    plants = list(capacities.keys())
    regions = list(demands.keys())
    
    # --- NEW: AI Dynamic Safety Stock Injection ---
    if high_risk_regions is None:
        high_risk_regions = []
        
    adjusted_demands = {}
    for r in regions:
        if r in high_risk_regions:
            # Inject a 10% buffer if region is flagged by the ML Risk Classifier
            adjusted_demands[r] = demands[r] * 1.10 
        else:
            adjusted_demands[r] = demands[r]
    
    # Decision Variables: Units assigned per route
    route_vars = LpVariable.dicts("Route", (plants, regions), lowBound=0)
    
    # Core Cost Objective Function
    prob += lpSum([route_vars[p][r] * cost_matrix[p][r] for p in plants for r in regions])
    
    # Constraint 1: Supply coming out of factories cannot breach maximum capabilities
    for p in plants:
        prob += lpSum([route_vars[p][r] for r in regions]) <= capacities[p]
        
    # Constraint 2: Global regional orders must be fully fulfilled (using AI buffered demand)
    for r in regions:
        prob += lpSum([route_vars[p][r] for p in plants]) >= adjusted_demands[r]
        
    prob.solve()
    
    allocations = {p: {r: float(route_vars[p][r].varValue or 0.0) for r in regions} for p in plants}
    
    return {
        "status": "Optimal" if prob.status == 1 else "Infeasible / Unbounded",
        "buffered_demands_used": adjusted_demands,
        "allocations": allocations
    }