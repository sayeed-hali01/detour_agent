import os
import math
import httpx
import polyline
from utils.polyline_utils import haversine_distance

# Mock coordinates database for fallback testing
CITY_COORDS = {
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "goa": (15.2993, 74.1240),
    "panaji": (15.4909, 73.8278),
    "panjim": (15.4909, 73.8278),
    "tumakuru": (13.3379, 77.1173),
    "tumkur": (13.3379, 77.1173),
    "chitradurga": (14.2251, 76.4000),
    "davanagere": (14.4644, 75.9218),
    "hubli": (15.3647, 75.1240),
    "hubballi": (15.3647, 75.1240),
    "dharwad": (15.4589, 75.0078),
    "ponda": (15.4005, 74.0040),
    "belagavi": (15.8497, 74.4977),
    "belgaum": (15.8497, 74.4977),
    "karwar": (14.8085, 74.1300),
}

def _resolve_coordinate(address: str) -> tuple[float, float]:
    """Resolves an address to a coordinate tuple using local lookup or default."""
    address_lower = address.lower()
    for name, coords in CITY_COORDS.items():
        if name in address_lower:
            return coords
    
    # Try parsing comma separated float coords if available
    try:
        parts = address.split(",")
        if len(parts) == 2:
            return (float(parts[0].strip()), float(parts[1].strip()))
    except ValueError:
        pass
        
    # Default to Bangalore coordinates
    return (12.9716, 77.5946)

def _generate_mock_route(origin: str, destination: str) -> dict:
    """Generates mock route info when Google API Key is unavailable."""
    origin_coord = _resolve_coordinate(origin)
    dest_coord = _resolve_coordinate(destination)
    
    # Estimate distance (haversine with a 1.25x road factor)
    base_dist = haversine_distance(origin_coord, dest_coord)
    distance_km = round(base_dist * 1.25, 2)
    
    # Estimate duration (average 80 km/h speed)
    duration_mins = round((distance_km / 80.0) * 60, 1)
    
    # Generate mock coordinates path
    num_points = 50
    coords = []
    lat1, lon1 = origin_coord
    lat2, lon2 = dest_coord
    
    for i in range(num_points):
        t = i / (num_points - 1)
        # Linear interpolation
        lat = lat1 + t * (lat2 - lat1)
        lon = lon1 + t * (lon2 - lon1)
        # Add a slight curve so it doesn't look like a straight line
        offset = 0.05 * math.sin(t * math.pi * 4)
        lat += offset
        lon += offset * 0.5
        coords.append((lat, lon))
        
    encoded_polyline = polyline.encode(coords)
    
    return {
        "origin": origin,
        "destination": destination,
        "distance_km": distance_km,
        "duration_mins": duration_mins,
        "polyline": encoded_polyline,
        "success": True,
        "is_mock": True
    }

async def get_route(origin: str, destination: str) -> dict:
    """Calculates route details between origin and destination, including duration, distance, and polyline.
    
    Args:
        origin: The starting address or coordinates, e.g. "San Francisco, CA".
        destination: The ending address or coordinates, e.g. "Los Angeles, CA".
        
    Returns:
        A dictionary containing:
        - origin: Address
        - destination: Address
        - distance_km: Distance in km
        - duration_mins: Duration in minutes
        - polyline: Encoded polyline string
        - success: Boolean status
        - is_mock: Boolean status
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return _generate_mock_route(origin, destination)
        
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "key": api_key
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            
        if response.status_code != 200:
            print(f"Maps API returned error status: {response.status_code}")
            return _generate_mock_route(origin, destination)
            
        data = response.json()
        if data.get("status") != "OK" or not data.get("routes"):
            print(f"Maps API status: {data.get('status')}. Falling back to mock.")
            return _generate_mock_route(origin, destination)
            
        route = data["routes"][0]
        leg = route["legs"][0]
        
        distance_km = round(leg["distance"]["value"] / 1000.0, 2)
        duration_mins = round(leg["duration"]["value"] / 60.0, 1)
        encoded_polyline = route["overview_polyline"]["points"]
        
        return {
            "origin": leg.get("start_address", origin),
            "destination": leg.get("end_address", destination),
            "distance_km": distance_km,
            "duration_mins": duration_mins,
            "polyline": encoded_polyline,
            "success": True,
            "is_mock": False
        }
    except Exception as e:
        print(f"Exception during routing: {e}. Falling back to mock.")
        return _generate_mock_route(origin, destination)

def get_route_agent_config() -> LocalAgentConfig:
    """Returns the LocalAgentConfig for the Route Agent."""
    return LocalAgentConfig(
        model="gemini-3.5-flash",
        system_instructions=(
            "You are the Route Agent. Your role is to determine the optimal route "
            "between two coordinates or city addresses. You can call the get_route "
            "tool to fetch detailed paths, durations, distances, and polylines. "
            "Always prioritize returning structured information about travel distance and time."
        ),
        tools=[get_route]
    )
