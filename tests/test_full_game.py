"""Test script for running a full 5-turn game and verifying all mechanics."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()  # This loads the .env file

from src.graph.game_graph import game_graph
from src.models import create_initial_game_state
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_full_game():
    """Run a complete 5-turn game and verify mechanics."""
    print("🧪 Running Full Game Test - 5 Turns, 3 Players\n")
    print("="*60)
    
    # Create initial game state
    initial_state = create_initial_game_state()
    
    # Configure for exactly 5 rounds (15 total turns)
    config = {
        "recursion_limit": 120,  # Enough for full game
        "configurable": {
            "thread_id": f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        }
    }
    
    # Run the complete game
    print("Starting game simulation...\n")
    final_state = game_graph.invoke(initial_state, config=config)
    
    # Analyze results
    print("\n" + "="*60)
    print("📊 GAME ANALYSIS")
    print("="*60)
    
    # 1. Verify turn count
    expected_turns = 15  # 5 rounds × 3 players
    actual_turns = final_state["turn_number"]
    print(f"\n✅ Turn Count: {actual_turns}/{expected_turns} turns completed")
    assert actual_turns == expected_turns, f"Expected {expected_turns} turns, got {actual_turns}"
    
    # 2. Check final scores and emotions
    print("\n📈 Final Player States:")
    for player_id, player in final_state["players"].items():
        emotion_icon = "😠" if player["emotion"].value == "angry" else "😐"
        print(f"  {player_id}: {player['points']} points {emotion_icon} ({player['emotion'].value})")
    
    # 3. Analyze emotion changes
    emotion_changes = [
        entry for entry in final_state["game_log"] 
        if entry["event_type"] == "emotion_change"
    ]
    print(f"\n😤 Emotion Changes: {len(emotion_changes)} total")
    
    if emotion_changes:
        print("\n  Emotion Change Details:")
        for change in emotion_changes[:5]:  # Show first 5
            details = change["details"]
            print(f"    Turn {change['turn']}: {change['player_id']} "
                  f"{details['old_emotion']} → {details['new_emotion']} "
                  f"(caused by {details['caused_by']})")
        if len(emotion_changes) > 5:
            print(f"    ... and {len(emotion_changes) - 5} more")
    
    # 4. Count extraction levels used
    extraction_counts = {1: 0, 2: 0, 3: 0}
    for player in final_state["players"].values():
        for action in player["action_history"]:
            # Handle both old and new field names for compatibility
            level = action.get("level", action.get("extraction_level", 1))
            if hasattr(level, 'value'):
                level = level.value
            extraction_counts[level] += 1
    
    print("\n🎯 Extraction Level Distribution:")
    for level, count in extraction_counts.items():
        percentage = (count / sum(extraction_counts.values())) * 100
        bar = "█" * int(percentage / 5)
        print(f"  Level {level}: {count:2d} times ({percentage:5.1f}%) {bar}")
    
    # 5. Check pain dynamics
    pain_events = []
    for player in final_state["players"].values():
        for action in player["action_history"]:
            if action["pain_caused_to"]:
                # Handle both old and new field names
                level = action.get("level", action.get("extraction_level", 1))
                if hasattr(level, 'value'):
                    level = level.value
                pain_events.append({
                    "turn": action["turn"],
                    "inflictor": action["player_id"],
                    "victims": action["pain_caused_to"],
                    "level": level
                })
    
    print(f"\n💥 Pain Events: {len(pain_events)} total")
    if pain_events:
        print("\n  Sample Pain Events:")
        for event in pain_events[:3]:
            intensity = "INTENSE" if event["level"] == 3 else "mild"
            print(f"    Turn {event['turn']}: {event['inflictor']} caused {intensity} pain "
                  f"to {', '.join(event['victims'])}")
    
    # 6. Verify game mechanics
    print("\n✅ Mechanics Verification:")
    
    # Check points calculation
    total_points = sum(p["points"] for p in final_state["players"].values())
    expected_min = 15  # At least 1 point per turn
    print(f"  Points System: {'✓' if total_points >= expected_min else '✗'} "
          f"(Total: {total_points} points)")
    
    # Check emotion system
    angry_players = sum(1 for p in final_state["players"].values() 
                       if p["emotion"].value == "angry")
    print(f"  Emotion System: {'✓' if emotion_changes else '✗'} "
          f"({angry_players} angry players at end)")
    
    # Check adjacency
    adjacency_correct = all(
        len(p["adjacent_players"]) == 2 
        for p in final_state["players"].values()
    )
    print(f"  Adjacency: {'✓' if adjacency_correct else '✗'} "
          f"(All players have 2 neighbors)")
    
    # 7. Interesting patterns
    print("\n🔍 Interesting Patterns:")
    
    # Revenge cycles?
    revenge_count = 0
    for i, player in enumerate(final_state["players"].values()):
        if player["emotion"].value == "angry":
            # Count how many Level 3s they chose while angry
            angry_level3s = sum(
                1 for action in player["action_history"]
                if (action.get("level", action.get("extraction_level", 0)) == 3 or 
                    (hasattr(action.get("level", action.get("extraction_level", 0)), 'value') and 
                     action.get("level", action.get("extraction_level", 0)).value == 3)) and 
                any(e["turn"] < action["turn"] and e["player_id"] == player["id"]
                    for e in emotion_changes if e["details"]["new_emotion"] == "angry")
            )
            if angry_level3s > 0:
                revenge_count += angry_level3s
    
    print(f"  Revenge Actions: ~{revenge_count} Level 3 extractions by angry players")
    
    # Emotional contagion
    if emotion_changes:
        turns_with_changes = set(e["turn"] for e in emotion_changes)
        print(f"  Emotional Volatility: Changes occurred in {len(turns_with_changes)}/{expected_turns} turns")
    
    # Winner analysis
    scores = {pid: p["points"] for pid, p in final_state["players"].items()}
    winner = max(scores, key=scores.get)
    winner_emotion = final_state["players"][winner]["emotion"].value
    print(f"\n🏆 Winner: {winner} with {scores[winner]} points (emotion: {winner_emotion})")
    
    print("\n" + "="*60)
    print("✅ FULL GAME TEST COMPLETE")
    print("="*60)
    
    return final_state


def test_prompt_visibility():
    """Test that prompts are visible in the game state."""
    print("\n\n🔍 Testing Prompt Visibility\n")
    
    initial_state = create_initial_game_state()
    config = {"recursion_limit": 5}  # Just one turn
    
    # Stream to see prompts
    for event in game_graph.stream(initial_state, config=config):
        for node_name, node_output in event.items():
            if node_name == "get_player_decision" and node_output.get("current_player_prompt"):
                print(f"✅ Prompt found for {node_output['current_player_id']}:")
                print(f"   Length: {len(node_output['current_player_prompt'])} characters")
                print(f"   Preview: {node_output['current_player_prompt'][:100]}...")
                return True
    
    print("❌ No prompts found in game state!")
    return False


if __name__ == "__main__":
    # Run the full game test
    final_state = test_full_game()
    
    # Test prompt visibility
    test_prompt_visibility()
    
    print("\n🎉 All tests completed!") 