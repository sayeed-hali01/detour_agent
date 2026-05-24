from pydantic import BaseModel, Field
from google.antigravity import Agent, LocalAgentConfig

class RankedDetour(BaseModel):
    name: str = Field(..., description="Name of the place")
    place_id: str = Field(..., description="The unique place identifier from Google Maps")
    rating: float = Field(..., description="The average rating of the place, from 0.0 to 5.0")
    score: float = Field(..., description="Overall suitability score from 0.0 to 10.0 based on user preferences and convenience")
    reasoning: str = Field(..., description="Clear explanation of why this place is recommended for the user")
    category: str = Field(..., description="The category/type of this place")
    estimated_added_time_mins: float = Field(..., description="Heuristically estimated additional time (in minutes) for this detour (including travel and quick stop)")

class DetourRankingResponse(BaseModel):
    ranked_detours: list[RankedDetour] = Field(..., description="List of detours ordered from best to worst based on score")

def get_ranking_agent_config() -> LocalAgentConfig:
    """Returns the LocalAgentConfig for the Ranking Agent."""
    return LocalAgentConfig(
        model="gemini-3.5-flash",
        system_instructions=(
            "You are the Ranking Agent. Your job is to filter and prioritize a list "
            "of candidate detour locations (places) based on a traveler's preferences "
            "and time constraints. You will receive a list of locations and user interests, "
            "and output a structured list of recommendations sorted by suitability."
        ),
        response_schema=DetourRankingResponse
    )

import os
import random
import re

def _generate_mock_ranking(candidates: list[dict], user_preferences: str, max_detour_mins: float) -> dict:
    """Generates a heuristic-based mock ranking when Gemini API key is missing or fails."""
    # Extract keywords from user preferences
    keywords = re.findall(r'\w+', user_preferences.lower())
    
    ranked_list = []
    # Seed with the length of candidates to keep it deterministic per run
    random.seed(len(candidates))
    
    for item in candidates:
        rating = item.get("rating", 4.0)
        # Base score from rating
        score = rating * 1.5  # Max 7.5
        
        name_lower = item["name"].lower()
        cat_lower = item["category"].lower()
        
        # Check relevance to keywords
        relevance_bonus = 0.0
        matched_keywords = []
        for kw in keywords:
            if len(kw) > 3 and (kw in name_lower or kw in cat_lower):
                relevance_bonus += 0.8
                matched_keywords.append(kw)
                
        score += min(2.5, relevance_bonus)  # Max bonus 2.5
        score = round(min(10.0, score), 1)
        
        matched_str = f" relating to your interest in '{', '.join(matched_keywords)}'" if matched_keywords else ""
        reasoning = (
            f"Highly rated at {rating}★. Recommended because it fits your preference parameters{matched_str} "
            f"and provides a convenient detour option."
        )
        
        ranked_list.append({
            "name": item["name"],
            "place_id": item["place_id"],
            "rating": rating,
            "score": score,
            "reasoning": reasoning,
            "category": item["category"],
            "estimated_added_time_mins": round(random.uniform(5.0, max_detour_mins), 1)
        })
        
    # Sort by score descending
    ranked_list.sort(key=lambda d: d["score"], reverse=True)
    return {"ranked_detours": ranked_list}

async def rank_candidates(candidates: list[dict], user_preferences: str, max_detour_mins: float) -> dict:
    """Invokes the ranking agent to evaluate and score candidate places.
    
    Args:
        candidates: List of candidate place dictionaries.
        user_preferences: String description of traveler's interests.
        max_detour_mins: Maximum detour time budget.
        
    Returns:
        A dictionary matching the DetourRankingResponse schema.
    """
    if not candidates:
        return {"ranked_detours": []}
        
    # Heuristic fallback if API key is missing
    if not os.getenv("GEMINI_API_KEY"):
        print("Orchestrator [Ranking Agent]: GEMINI_API_KEY is missing. Falling back to Heuristic Ranker.")
        return _generate_mock_ranking(candidates, user_preferences, max_detour_mins)
        
    config = get_ranking_agent_config()
    
    prompt = f"""
    Evaluate and rank the following candidate places based on the user's preferences:
    
    User Preferences: "{user_preferences}"
    Detour Time Budget: {max_detour_mins} minutes
    
    Candidate Places:
    {candidates}
    
    Filter out any options that are obviously unsuitable. Sort the rest from best to worst.
    Ensure that you calculate a realistic 'score' between 0.0 and 10.0, and write a custom 
    'reasoning' block highlighting how the place aligns with their preferences.
    """
    
    try:
        async with Agent(config=config) as agent:
            response = await agent.chat(prompt)
            structured = await response.structured_output()
            if not structured or not structured.get("ranked_detours"):
                raise ValueError("Ranking agent returned empty or invalid structured output.")
            return structured
    except Exception as e:
        print(f"Orchestrator [Ranking Agent]: Agent call failed: {e}. Falling back to Heuristic Ranker.")
        return _generate_mock_ranking(candidates, user_preferences, max_detour_mins)

