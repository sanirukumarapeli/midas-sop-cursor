from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from src.chat_agent import get_integrated_copilot_agent
from langchain_core.messages import HumanMessage, AIMessage

app = FastAPI(title="Midas S&OP AI Co-Pilot API", version="1.0")

# 🚨 CORS CONFIGURATION
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent_harness = get_integrated_copilot_agent()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    input: str
    chat_history: Optional[List[ChatMessage]] = []

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        formatted_history = []
        for msg in request.chat_history:
            if msg.role == "user":
                formatted_history.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                formatted_history.append(AIMessage(content=msg.content))
                
        response = agent_harness.invoke({
            "input": request.input,
            "chat_history": formatted_history
        })
        
        # 🚨 THE FIX (Step 5): response["output"] is already a validated dictionary now. 
        # No parsing, regex, or backtick-stripping needed.
        structured_payload = dict(response.get("output", {}))
        
        # Attach the extracted token usage
        structured_payload["usage"] = response.get("usage", {})
        
        return structured_payload
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backend execution failure: {str(e)}")

@app.post("/api/retrain")
async def trigger_retraining():
    try:
        import src.data_query
        from src.train import train_and_serialize_models
        
        src.data_query._DATA_CACHE = None 
        train_and_serialize_models()
        
        return {"status": "success", "message": "Models retrained successfully on live database!"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model Retraining Failed: {str(e)}")
    
@app.post("/api/reset")
async def reset_copilot_memory():
    try:
        import src.data_query
        src.data_query._DATA_CACHE = None 
        return {"status": "success", "message": "Core LLM memory wiped clean."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear memory: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)