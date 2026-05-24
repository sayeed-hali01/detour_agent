# Detour Agent Backend

Detour Agent Backend is a multi-agent system designed to find, rank, and plan detours (points of interest/POIs) along a user's road trip route. It uses the **Google Antigravity (AGY) SDK** to coordinate multiple specialized agents to produce a tailored itinerary.

## Architecture

The backend consists of:
- **`orchestrator/root_agent.py`**: The primary coordinator agent that receives user requests, spawns subagents, parses/translates their responses, and produces the final itinerary.
- **`agents/route_agent.py`**: An agent that interacts with routing services to calculate base routes and detour routing options.
- **`agents/places_agent.py`**: An agent that queries places APIs to search for points of interest near coordinates along the route.
- **`agents/ranking_agent.py`**: An agent that analyzes user preferences and ranks candidate places with custom reasoning, returning a structured JSON output.
- **`utils/polyline_utils.py`**: Polyline encoding/decoding and coordinate sampling utilities.
- **`api/main.py`**: A FastAPI application providing endpoints to interact with the multi-agent planning engine.

## Setup

1. **Prerequisites**: Python 3.10+
2. **Environment Variables**:
   Create a `.env` file at the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key_or_mock
   PORT=8000
   ```

3. **Install Dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run Server**:
   ```bash
   uvicorn api.main:app --port 8000 --reload
   ```

## API Endpoints

- `GET /api/tour`: tour status.
- `POST /api/detour-plan`: Plan a route with detours.
  - Body:
    ```json
    {
      "origin": "San Francisco, CA",
      "destination": "Los Angeles, CA",
      "categories": ["scenic_lookout", "cafe"],
      "max_detour_minutes": 30,
      "user_preferences": "I like historic monuments, ocean views, and specialty espresso."
    }
    ```
