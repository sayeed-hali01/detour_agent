import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from orchestrator.root_agent import run_orchestration

app = FastAPI(
    title="Detour Agent API",
    description="Multi-agent road trip detour planner built with Google Antigravity SDK",
    version="1.0.0"
)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DetourRequest(BaseModel):
    origin: str = Field(..., description="Starting point address or coordinates", json_schema_extra={"example": "San Francisco, CA"})
    destination: str = Field(..., description="Ending point address or coordinates", json_schema_extra={"example": "Los Angeles, CA"})
    categories: list[str] = Field(
        default=["cafe", "tourist_attraction"],
        description="List of categories to search for, e.g. 'cafe', 'scenic_lookout', 'park'",
        json_schema_extra={"example": ["cafe", "scenic_lookout"]}
    )
    max_detour_minutes: float = Field(
        default=30.0,
        description="Maximum extra duration budget in minutes allowed for the detour",
        json_schema_extra={"example": 30.0}
    )
    user_preferences: str = Field(
        default="I like scenic drives, nature views, and specialty espresso.",
        description="Text description of specific traveler preferences to help rank places",
        json_schema_extra={"example": "I like historic monuments and specialty coffee."}
    )

@app.get("/api/health")
def health_check():
    """Basic health check endpoint that also reports credential configurations."""
    return {
        "status": "healthy",
        "gemini_api_key_configured": bool(os.getenv("GEMINI_API_KEY")),
        "google_maps_api_key_configured": bool(os.getenv("GOOGLE_MAPS_API_KEY"))
    }

@app.post("/api/detour-plan")
async def plan_detour(request: DetourRequest):
    """Calculates baseline route and discovers/ranks optimal detour opportunities."""
    # Ensure Gemini API Key is configured for Agent reasoning
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY environment variable is not configured. Please set it in your .env file."
        )
        
    try:
        plan = await run_orchestration(
            origin=request.origin,
            destination=request.destination,
            categories=request.categories,
            max_detour_minutes=request.max_detour_minutes,
            user_preferences=request.user_preferences
        )
        if not plan.get("success", False):
            raise HTTPException(
                status_code=400,
                detail=plan.get("error", "An error occurred during detour route calculation.")
            )
        return plan
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during coordination: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
