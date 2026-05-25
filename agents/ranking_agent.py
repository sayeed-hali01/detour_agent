import os
import random
import re
import json

from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class RankedDetour(BaseModel):
    name: str = Field(..., description="Name of the place")
    place_id: str = Field(..., description="The unique place identifier")
    rating: float = Field(..., description="Rating from 0.0 to 5.0")
    score: float = Field(..., description="Suitability score from 0.0 to 10.0")
    reasoning: str = Field(..., description="Why this place is recommended")
    category: str = Field(..., description="Category/type of this place")
    estimated_added_time_mins: float = Field(..., description="Estimated additional time in minutes")


def _generate_mock_ranking(candidates, user_preferences, max_detour_mins):
    keywords = re.findall(r'\w+', user_preferences.lower())
    ranked_list = []
    random.seed(len(candidates))
    for item in candidates:
        rating = item.get("rating", 4.0)
        score = rating * 1.5
        name_lower = item["name"].lower()
        cat_lower = item["category"].lower()
        relevance_bonus = 0.0
        matched_keywords = []
        for kw in keywords:
            if len(kw) > 3 and (kw in name_lower or kw in cat_lower):
                relevance_bonus += 0.8
                matched_keywords.append(kw)
        score += min(2.5, relevance_bonus)
        score = round(min(10.0, score), 1)
        matched_str = f" relating to your interest in '{', '.join(matched_keywords)}'" if matched_keywords else ""
        reasoning = f"Highly rated at {rating}. Recommended because it fits your preferences{matched_str}."
        ranked_list.append({
            "name": item["name"],
            "place_id": item["place_id"],
            "rating": rating,
            "score": score,
            "reasoning": reasoning,
            "category": item["category"],
            "estimated_added_time_mins": round(random.uniform(5.0, max_detour_mins), 1)
        })
    ranked_list.sort(key=lambda d: d["score"], reverse=True)
    return {"ranked_detours": ranked_list}


async def rank_candidates(candidates, user_preferences, max_detour_mins):
    if not candidates:
        return {"ranked_detours": []}
    return _generate_mock_ranking(candidates, user_preferences, max_detour_mins)
    prompt = f"""
Evaluate and rank the following candidate places based on the user preferences.
User Preferences: "{user_preferences}"
Detour Time Budget: {max_detour_mins} minutes
Candidate Places:
{json.dumps(candidates, indent=2)}
Return a JSON object with a "ranked_detours" array. Each item must have:
- name (string)
- place_id (string)
- rating (float)
- score (float 0.0-10.0)
- reasoning (string)
- category (string)
- estimated_added_time_mins (float)
Return ONLY valid JSON, no extra text.
"""
    try:
        agent = LlmAgent(
            model="gemini-2.5-flash",
            name="ranking_agent",
            instruction="You are the Ranking Agent. Return only valid JSON."
        )
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name="detour_planner",
            user_id="ranking_user",
            session_id="ranking_session"
        )
        runner = Runner(
            agent=agent,
            app_name="detour_planner",
            session_service=session_service
        )
        message = types.Content(role="user", parts=[types.Part(text=prompt)])
        full_response = ""
        async for event in runner.run_async(
            user_id="ranking_user",
            session_id="ranking_session",
            new_message=message
        ):
            if event.is_final_response() and event.content and event.content.parts:
                full_response = event.content.parts[0].text
                break
        if not full_response:
            raise ValueError("Empty response from ranking agent.")
        clean = full_response.strip()
        if clean.startswith("```"):
            clean = re.sub(r'^```[a-z]*\n?', '', clean)
            clean = re.sub(r'\n?```$', '', clean)
        structured = json.loads(clean)
        if not structured.get("ranked_detours"):
            raise ValueError("Empty ranked_detours.")
        return structured
    except Exception as e:
        print(f"Ranking agent failed: {e}. Using heuristic ranker.")
        return _generate_mock_ranking(candidates, user_preferences, max_detour_mins)
