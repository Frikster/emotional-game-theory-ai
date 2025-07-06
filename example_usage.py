"""Example usage of the Emotional Game Theory graph."""
from src.graph.game_graph import game_graph
from src.models import create_initial_game_state
import json
import os
from datetime import datetime


def run_example_game(enable_tracing=True):
    """Run an example game and display results.
    
    Args:
        enable_tracing: If True, enables LangSmith tracing
    """
    print("🎮 Starting Emotional Game Theory Simulation\n")
    
    # Create initial game state
    initial_state = create_initial_game_state()
    
    # Generate a unique thread ID for this game
    thread_id = f"game-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Configure the graph execution
    config = {
        "recursion_limit": 120,  # Enough for 15 turns (5 nodes per turn + handle_input)
        "configurable": {
            "thread_id": thread_id  # Unique thread for LangSmith tracking
        }
    }
    
    # Enable LangSmith tracing if requested
    if enable_tracing and os.getenv("LANGCHAIN_API_KEY"):
        config["callbacks"] = []  # LangSmith will auto-attach if env vars are set
        print(f"📊 LangSmith tracing enabled - Thread ID: {thread_id}")
        print(f"   View in LangSmith: https://smith.langchain.com/projects")
        print()
    
    # Option 1: Run the entire game and get final state
    print("Running complete game...")
    final_state = game_graph.invoke(initial_state, config=config)
    
    # Display results
    print("\n📊 Final Game Results:")
    print("-" * 40)
    
    for player_id, player in final_state["players"].items():
        emotion_icon = "😠" if player["emotion"] == "angry" else "😐"
        print(f"{player_id}: {player['points']} points {emotion_icon} {player['emotion']}")
    
    # Show winner
    scores = {pid: p["points"] for pid, p in final_state["players"].items()}
    winner = max(scores, key=scores.get)
    print(f"\n🏆 Winner: {winner} with {scores[winner]} points!")
    
    # Show some interesting statistics
    print("\n📈 Game Statistics:")
    print(f"Total turns played: {final_state['turn_number']}")
    
    # Count emotion changes
    emotion_changes = [e for e in final_state["game_log"] 
                      if e["event_type"] == "emotion_change"]
    print(f"Total emotion changes: {len(emotion_changes)}")
    
    # Count extraction levels
    extractions = {}
    for player in final_state["players"].values():
        for action in player["action_history"]:
            level = action["extraction_level"]
            extractions[level] = extractions.get(level, 0) + 1
    
    print("\nExtraction level distribution:")
    for level, count in sorted(extractions.items()):
        print(f"  Level {level}: {count} times")


def stream_example_game(enable_tracing=True):
    """Example of streaming game events in real-time.
    
    Args:
        enable_tracing: If True, enables LangSmith tracing
    """
    print("\n\n🎮 Streaming Game Events\n")
    
    initial_state = create_initial_game_state()
    thread_id = f"stream-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    config = {
        "recursion_limit": 20,  # Just a few turns for demo
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    if enable_tracing and os.getenv("LANGCHAIN_API_KEY"):
        config["callbacks"] = []
        print(f"📊 Streaming with LangSmith - Thread ID: {thread_id}\n")
    
    turn_count = 0
    for event in game_graph.stream(initial_state, config=config):
        turn_count += 1
        
        # Each event is a dict with node name as key
        for node_name, node_output in event.items():
            if node_name == "get_player_decision":
                player = node_output["current_player_id"]
                action = node_output["current_action"]
                if action:
                    print(f"Turn {action['turn']}: {player} extracts level {action['extraction_level']}")
            
            elif node_name == "apply_action" and node_output.get("current_action"):
                action = node_output["current_action"]
                if action["pain_caused_to"]:
                    print(f"         → Caused pain to: {', '.join(action['pain_caused_to'])}")
                if action["emotion_changes"]:
                    for pid, emotion in action["emotion_changes"].items():
                        print(f"         → {pid} is now {emotion}!")
        
        if turn_count >= 9:  # Show 3 complete turns (3 players × 3 nodes)
            print("\n... (streaming continues)")
            break


def setup_langsmith_tracing():
    """Setup LangSmith tracing by configuring environment variables."""
    # Check if LangSmith is configured
    if os.getenv("LANGSMITH_API_KEY"):
        # Enable tracing
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = "emotional-game-theory"
        print("✅ LangSmith tracing is configured!")
        print("   Project: emotional-game-theory")
        print("   View traces at: https://smith.langchain.com\n")
        return True
    else:
        print("⚠️  LangSmith tracing not configured.")
        print("   To enable tracing, set these environment variables:")
        print("   - LANGCHAIN_API_KEY: Your LangSmith API key")
        print("   - LANGCHAIN_ENDPOINT: https://api.smith.langchain.com (optional)")
        print("\n   Get your API key at: https://smith.langchain.com\n")
        return False


if __name__ == "__main__":
    # Setup LangSmith tracing if available
    tracing_enabled = setup_langsmith_tracing()
    
    # Run a complete game
    run_example_game(enable_tracing=tracing_enabled)
    
    # Show streaming example
    stream_example_game(enable_tracing=tracing_enabled) 