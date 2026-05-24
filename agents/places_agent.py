import os
import random
import httpx
from google.antigravity import LocalAgentConfig

# Mock data for generating realistic POIs based on categories
MOCK_PLACES_POOL = {
    "cafe": [
        "Coastal Coffee House", "Redwood Roast Espresso", "Summit View Cafe",
        "Wayside Roasters", "The Daily Grind", "Highway Espresso Bar"
    ],
    "coffee": [
        "Coastal Coffee House", "Redwood Roast Espresso", "Summit View Cafe",
        "Wayside Roasters", "The Daily Grind", "Highway Espresso Bar"
    ],
    "restaurant": [
        "Pacific Coast Grill", "The Scenic Diner", "Mountain Ridge Steakhouse",
        "Valley Vineyards Bistro", "Roadside Burger Joint", "Forest Canopy Kitchen"
    ],
    "scenic_lookout": [
        "Ocean Vista Point", "Sunset Peak Overlook", "Valley Canopy Observation Deck",
        "Golden Gate Ridge Lookout", "Pacific Horizons Vista", "Pine Crest Ridge View"
    ],
    "tourist_attraction": [
        "Historic Coastal Lighthouse", "Mystery Redwood Forest Path", "Pioneer Pioneer Memorial",
        "Old Mill Historic Site", "Grizzly Peak State Reserve", "Whispering Falls Park"
    ],
    "park": [
        "Redwood Valley State Park", "Ocean Shoreline Reserve", "Meadowcreek Park",
        "Sentinel Peak Trailhead", "Sunny Pines Campground", "Canyon Creek Meadows"
    ],
    "gas_station": [
        "Highway Shell & Shop", "Chevron Express Way", "Roadside Travel Plaza",
        "EcoFuel Charging & Fuel"
    ]
}

def _generate_mock_places(latitude: float, longitude: float, category: str) -> list[dict]:
    """Generates mock places near a coordinate when Google Places API key is missing."""
    category_key = category.lower()
    # Find matching pool or default to tourist_attraction
    pool = MOCK_PLACES_POOL.get(category_key)
    if not pool:
        # Check substring match
        for key in MOCK_PLACES_POOL:
            if key in category_key:
                pool = MOCK_PLACES_POOL[key]
                break
        if not pool:
            pool = MOCK_PLACES_POOL["tourist_attraction"]
            
    # Select 2-3 places from the pool
    random.seed(hash((latitude, longitude, category)))
    num_places = random.randint(2, 3)
    places = []
    
    selected_names = random.sample(pool, min(num_places, len(pool)))
    for i, name in enumerate(selected_names):
        # Generate small offset (approx. within 2-5 km)
        lat_offset = random.uniform(-0.02, 0.02)
        lon_offset = random.uniform(-0.02, 0.02)
        
        place_lat = round(latitude + lat_offset, 5)
        place_lon = round(longitude + lon_offset, 5)
        rating = round(random.uniform(4.1, 4.9), 1)
        ratings_count = random.randint(40, 1800)
        
        places.append({
            "name": name,
            "address": f"Near highway coordinate ({latitude:.4f}, {longitude:.4f})",
            "latitude": place_lat,
            "longitude": place_lon,
            "rating": rating,
            "user_ratings_total": ratings_count,
            "category": category,
            "place_id": f"mock_place_{category}_{int((place_lat + place_lon)*1000000)}",
            "is_mock": True
        })
    return places

async def search_places_near_coordinate(latitude: float, longitude: float, category: str, radius: int = 5000) -> list[dict]:
    """Searches for points of interest (POIs) of a given category within a radius of a specific coordinate.
    
    Args:
        latitude: Latitude coordinate of search center.
        longitude: Longitude coordinate of search center.
        category: Search keyword or category, e.g. "cafe", "scenic_lookout", "park".
        radius: Search radius in meters. Default is 5000 (5km).
        
    Returns:
        A list of dictionaries representing matching places:
        - name: String name
        - address: String address
        - latitude: Float latitude
        - longitude: Float longitude
        - rating: Float review score (0.0 to 5.0)
        - user_ratings_total: Integer number of reviews
        - category: String category
        - place_id: String unique identifier
        - is_mock: Boolean status
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return _generate_mock_places(latitude, longitude, category)
        
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{latitude},{longitude}",
        "radius": radius,
        "keyword": category,
        "key": api_key
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            
        if response.status_code != 200:
            print(f"Places API returned error status: {response.status_code}")
            return _generate_mock_places(latitude, longitude, category)
            
        data = response.json()
        if data.get("status") not in ["OK", "ZERO_RESULTS"]:
            print(f"Places API status: {data.get('status')}. Falling back to mock.")
            return _generate_mock_places(latitude, longitude, category)
            
        results = data.get("results", [])
        places = []
        
        for item in results[:5]:  # Limit to top 5 places per coordinate sample
            loc = item["geometry"]["location"]
            places.append({
                "name": item.get("name"),
                "address": item.get("vicinity", "Address unknown"),
                "latitude": loc["lat"],
                "longitude": loc["lng"],
                "rating": item.get("rating", 4.0),
                "user_ratings_total": item.get("user_ratings_total", 0),
                "category": category,
                "place_id": item.get("place_id"),
                "is_mock": False
            })
            
        return places
    except Exception as e:
        print(f"Exception during place search: {e}. Falling back to mock.")
        return _generate_mock_places(latitude, longitude, category)

def get_places_agent_config() -> LocalAgentConfig:
    """Returns the LocalAgentConfig for the Places Agent."""
    return LocalAgentConfig(
        model="gemini-3.5-flash",
        system_instructions=(
            "You are the Places Agent. Your role is to identify and discover points of "
            "interest (POIs) along a travel route. You can query the search_places_near_coordinate "
            "tool to search for attractions, cafes, rest stops, or scenic spots near coordinates "
            "along a primary route. Ensure you collect information on ratings and descriptions."
        ),
        tools=[search_places_near_coordinate]
    )
