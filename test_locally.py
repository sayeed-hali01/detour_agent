import asyncio
import json
from orchestrator.root_agent import run_orchestration

async def test_detour_planning():
    print("=== Detour Backend Local Verification ===")
    
    # Define test parameters
    origin = "San Francisco, CA"
    destination = "Los Angeles, CA"
    categories = ["cafe", "scenic_lookout"]
    max_detour_minutes = 30.0
    user_preferences = "I want nice views of the ocean, historic places, and delicious coffee."
    
    print(f"Planning route from: {origin}")
    print(f"To: {destination}")
    print(f"Categories: {categories}")
    print(f"Max Detour Budget: {max_detour_minutes} minutes")
    print(f"Preferences: '{user_preferences}'")
    print("-" * 50)
    
    try:
        # Run the full orchestrator pipeline
        plan = await run_orchestration(
            origin=origin,
            destination=destination,
            categories=categories,
            max_detour_minutes=max_detour_minutes,
            user_preferences=user_preferences
        )
        
        print("\n=== Plan Result ===")
        print(json.dumps(plan, indent=2))
        
        if plan.get("success"):
            print("\nSUCCESS: Multi-agent coordination executed and returned a valid itinerary plan!")
        else:
            print(f"\nFAILURE: Coordination failed with error: {plan.get('error')}")
            
    except Exception as e:
        print(f"\nERROR: Exception occurred during local test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_detour_planning())
