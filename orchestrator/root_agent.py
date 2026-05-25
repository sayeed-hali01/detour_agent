
from agents.route_agent import get_route
from agents.places_agent import search_places_near_coordinate
from agents.ranking_agent import rank_candidates
from utils.polyline_utils import decode_polyline, sample_coords_from_polyline

def get_root_agent_config() -> LocalAgentConfig:
    """Returns the LocalAgentConfig for the Root Orchestrator Agent."""
    return LocalAgentConfig(
        model="gemini-3.5-flash",
        system_instructions=(
            "You are the Root Detour Orchestrator Agent. Your task is to coordinate the "
            "Route Agent, Places Agent, and Ranking Agent to plan a customized road trip "
            "itinerary. You receive requests detailing an origin, destination, categories "
            "of interest, detour budgets, and personal preferences, and return a structured "
            "travel plan."
        )
    )

async def run_orchestration(
    origin: str,
    destination: str,
    categories: list[str],
    max_detour_minutes: float,
    user_preferences: str
) -> dict:
    """Coordinates the full multi-agent workflow to find and plan optimal detours.
    
    Workflow:
    1. Spawns Route Agent to get the primary route.
    2. Decodes the polyline and samples points along the route.
    3. Spawns Places Agent to search for POIs near the sampled points.
    4. Deduplicates candidate places.
    5. Spawns Ranking Agent to score and prioritize candidates based on user preferences.
    6. Spawns Route Agent to calculate exact detour travel overhead for top candidates.
    7. Compiles and returns the final plan.
    
    Args:
        origin: Start address or coordinates.
        destination: End address or coordinates.
        categories: Categories of interest, e.g. ["cafe", "scenic_lookout"].
        max_detour_minutes: Detour budget in minutes.
        user_preferences: Personal interest details.
        
    Returns:
        A dictionary containing the compiled plan.
    """
    # Step 1: Get baseline route
    print(f"Orchestrator: Fetching baseline route from '{origin}' to '{destination}'...")
    base_route = await get_route(origin, destination)
    if not base_route.get("success"):
        return {
            "success": False,
            "error": "Failed to calculate baseline route. Please verify your origin and destination."
        }
        
    baseline_duration = base_route["duration_mins"]
    baseline_distance = base_route["distance_km"]
    baseline_polyline = base_route["polyline"]
    
    # Step 2: Decode and sample points along the route
    coords = decode_polyline(baseline_polyline)
    if not coords:
        return {
            "success": False,
            "error": "Failed to decode baseline route geometry."
        }
    
    # Dynamic sampling interval to get ~8 points along the route
    sample_interval = max(3, len(coords) // 8)
    sampled_coords = sample_coords_from_polyline(coords, sample_interval=sample_interval)
    # Safety limit to prevent excessive api calls
    sampled_coords = sampled_coords[:10]
    
    print(f"Orchestrator: Sampled {len(sampled_coords)} coordinates along the route for place discovery.")
    
    # Step 3: Search for candidate places near sampled points
    candidates = []
    for i, (lat, lon) in enumerate(sampled_coords):
        for category in categories:
            places = await search_places_near_coordinate(lat, lon, category)
            candidates.extend(places)
            
    # Deduplicate places by place_id
    seen_ids = set()
    deduped_candidates = []
    for item in candidates:
        pid = item.get("place_id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            deduped_candidates.append(item)
            
    print(f"Orchestrator: Found {len(deduped_candidates)} unique candidate places across all categories.")
    
    if not deduped_candidates:
        return {
            "success": True,
            "baseline_route": {
                "origin": base_route["origin"],
                "destination": base_route["destination"],
                "distance_km": baseline_distance,
                "duration_mins": baseline_duration,
                "polyline": baseline_polyline
            },
            "proposed_detours": [],
            "message": "No detours matching your selected categories were found along the route."
        }
        
    # Step 4: Rank candidates using Ranking Agent
    print("Orchestrator: Ranking candidate places using user preferences...")
    ranking_data = await rank_candidates(
        candidates=deduped_candidates,
        user_preferences=user_preferences,
        max_detour_mins=max_detour_minutes
    )
    
    ranked_detours = ranking_data.get("ranked_detours", [])
    print(f"Orchestrator: Ranking agent recommended {len(ranked_detours)} places.")
    
    # Create candidate map for easy lookup of coordinates/addresses
    candidates_map = {c["place_id"]: c for c in deduped_candidates}
    
    # Step 5: Calculate precise detour route overhead for top 3 candidates
    final_detours = []
    top_candidates = ranked_detours[:3]
    
    for rank, detour in enumerate(top_candidates, 1):
        place_id = detour.get("place_id") or detour.get("name") # Fallback to name if place_id missing
        orig_place = candidates_map.get(place_id)
        
        if not orig_place:
            # Try matching by name if place_id mapping failed
            for c in deduped_candidates:
                if c["name"] == detour.get("name"):
                    orig_place = c
                    break
                    
        if not orig_place:
            continue
            
        lat, lon = orig_place["latitude"], orig_place["longitude"]
        detour_location_str = f"{lat},{lon}"
        
        print(f"Orchestrator: Calculating precise detour route overhead for '{detour['name']}'...")
        # Leg 1: Origin to Detour Place
        leg1 = await get_route(origin, detour_location_str)
        # Leg 2: Detour Place to Destination
        leg2 = await get_route(detour_location_str, destination)
        
        if leg1.get("success") and leg2.get("success"):
            detour_dist = leg1["distance_km"] + leg2["distance_km"]
            detour_dur = leg1["duration_mins"] + leg2["duration_mins"]
            
            added_dist = round(max(0.0, detour_dist - baseline_distance), 2)
            added_dur = round(max(0.0, detour_dur - baseline_duration), 1)
            
            final_detours.append({
                "rank": rank,
                "name": orig_place["name"],
                "place_id": orig_place["place_id"],
                "address": orig_place["address"],
                "latitude": lat,
                "longitude": lon,
                "rating": orig_place["rating"],
                "user_ratings_total": orig_place["user_ratings_total"],
                "category": orig_place["category"],
                "score": detour["score"],
                "reasoning": detour["reasoning"],
                "added_distance_km": added_dist,
                "added_duration_mins": added_dur,
                "total_route_distance_km": round(detour_dist, 2),
                "total_route_duration_mins": round(detour_dur, 1),
                "route_leg1_polyline": leg1["polyline"],
                "route_leg2_polyline": leg2["polyline"]
            })
            
    # Sort final detours by suitability score descending
    final_detours.sort(key=lambda d: d["score"], reverse=True)
    
    # Re-assign rankings post-sort
    for idx, detour in enumerate(final_detours, 1):
        detour["rank"] = idx
        
    return {
        "success": True,
        "baseline_route": {
            "origin": base_route["origin"],
            "destination": base_route["destination"],
            "distance_km": baseline_distance,
            "duration_mins": baseline_duration,
            "polyline": baseline_polyline
        },
        "proposed_detours": final_detours
    }
