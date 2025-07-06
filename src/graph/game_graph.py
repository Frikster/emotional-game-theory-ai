"""Main game graph using LangGraph for turn-based game flow."""
from typing import Literal, Optional
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from src.models import GameState, ActionRecord, GameLogEntry, create_initial_game_state
from src.types import MAX_TURNS, Emotion, EXTRACTION_EFFECTS


def start_turn(state: GameState) -> GameState:
    """Initialize a new turn and select the next player."""
    import copy
    
    # Create a deep copy to avoid mutation
    new_state = copy.deepcopy(state)
    
    # Increment turn number
    new_turn = new_state["turn_number"] + 1
    
    # Determine current player (cycle through players)
    player_ids = list(new_state["players"].keys())
    current_player_index = (new_turn - 1) % len(player_ids)
    current_player_id = player_ids[current_player_index]
    
    # Add log entry
    new_state["game_log"].append(
        GameLogEntry(
            turn=new_turn,
            event_type="action",
            player_id=current_player_id,
            message=f"Turn {new_turn} started - {current_player_id}'s turn",
            details={"player_order": player_ids}
        )
    )
    
    new_state["turn_number"] = new_turn
    new_state["current_player_id"] = current_player_id
    new_state["current_action"] = None
    new_state["pending_emotion_updates"] = {}
    
    return new_state


def get_player_decision(state: GameState) -> GameState:
    """Get the player's extraction level decision.
    
    Note: This is a placeholder that will be replaced with LLM call in Step 4.
    For now, it returns a mock decision.
    """
    import random
    import copy
    from src.types import ExtractionLevel
    
    # Create a deep copy to avoid mutation
    new_state = copy.deepcopy(state)
    
    current_player = new_state["players"][new_state["current_player_id"]]
    
    # Placeholder logic: angry players more likely to extract level 3
    if current_player["emotion"] == Emotion.ANGRY:
        extraction_level = random.choices(
            [ExtractionLevel.LEVEL_1, ExtractionLevel.LEVEL_2, ExtractionLevel.LEVEL_3],
            weights=[1, 2, 7]  # Heavily weighted towards level 3
        )[0]
    else:
        extraction_level = random.choices(
            [ExtractionLevel.LEVEL_1, ExtractionLevel.LEVEL_2, ExtractionLevel.LEVEL_3],
            weights=[3, 4, 3]  # Balanced choices
        )[0]
    
    # Log the decision
    new_state["game_log"].append(
        GameLogEntry(
            turn=new_state["turn_number"],
            event_type="action",
            player_id=new_state["current_player_id"],
            message=f"{new_state['current_player_id']} chose extraction level {extraction_level}",
            details={
                "emotion": current_player["emotion"],
                "extraction_level": extraction_level
            }
        )
    )
    
    # Create action record (to be processed in apply_action)
    effects = EXTRACTION_EFFECTS[extraction_level]
    action = ActionRecord(
        turn=new_state["turn_number"],
        player_id=new_state["current_player_id"],
        extraction_level=extraction_level,
        points_gained=effects["points"],
        pain_caused_to=[],  # Will be filled in apply_action
        emotion_changes={}   # Will be filled in apply_action
    )
    
    new_state["current_action"] = action
    
    return new_state


def apply_action(state: GameState) -> GameState:
    """Apply the chosen action, updating points and emotions."""
    import copy
    
    # Create a deep copy of the state to avoid mutation issues
    new_state = copy.deepcopy(state)
    
    action = new_state["current_action"]
    current_player_id = new_state["current_player_id"]
    
    # Update current player's points
    new_state["players"][current_player_id]["points"] += action["points_gained"]
    
    # Get extraction effects
    effects = EXTRACTION_EFFECTS[action["extraction_level"]]
    
    # Apply effects to adjacent players
    adjacent_players = new_state["players"][current_player_id]["adjacent_players"]
    pending_updates = {}
    pain_caused_to = []
    
    if effects["pain_intensity"] != "none":
        for adj_player_id in adjacent_players:
            pain_caused_to.append(adj_player_id)
            
            # Apply emotion changes for intense pain
            if effects["causes_anger"]:
                pending_updates[adj_player_id] = Emotion.ANGRY
                action["emotion_changes"][adj_player_id] = Emotion.ANGRY
    
    action["pain_caused_to"] = pain_caused_to
    
    # Add action to current player's history
    new_state["players"][current_player_id]["action_history"].append(action)
    
    # Log the effects
    if pain_caused_to:
        new_state["game_log"].append(
            GameLogEntry(
                turn=new_state["turn_number"],
                event_type="action",
                player_id=current_player_id,
                message=f"{current_player_id} caused {effects['pain_intensity']} pain to {', '.join(pain_caused_to)}",
                details={
                    "pain_intensity": effects["pain_intensity"],
                    "affected_players": pain_caused_to
                }
            )
        )
    
    # Apply pending emotion updates
    for player_id, new_emotion in pending_updates.items():
        old_emotion = new_state["players"][player_id]["emotion"]
        new_state["players"][player_id]["emotion"] = new_emotion
        
        new_state["game_log"].append(
            GameLogEntry(
                turn=new_state["turn_number"],
                event_type="emotion_change",
                player_id=player_id,
                message=f"{player_id}'s emotion changed from {old_emotion} to {new_emotion}",
                details={
                    "old_emotion": old_emotion,
                    "new_emotion": new_emotion,
                    "caused_by": current_player_id
                }
            )
        )
    
    return new_state


def check_game_end(state: GameState) -> GameState:
    """Check if the game should end."""
    import copy
    
    # Create a deep copy to avoid mutation
    new_state = copy.deepcopy(state)
    
    # Game ends after MAX_TURNS rounds (each player gets MAX_TURNS turns)
    total_turns_played = new_state["turn_number"]
    total_players = len(new_state["players"])
    
    if total_turns_played >= MAX_TURNS * total_players:
        new_state["is_game_over"] = True
        
        # Calculate final scores
        final_scores = {
            player_id: player["points"] 
            for player_id, player in new_state["players"].items()
        }
        
        winner = max(final_scores, key=final_scores.get)
        
        new_state["game_log"].append(
            GameLogEntry(
                turn=new_state["turn_number"],
                event_type="game_end",
                player_id=None,
                message=f"Game ended after {MAX_TURNS} rounds. Winner: {winner}",
                details={
                    "final_scores": final_scores,
                    "winner": winner,
                    "total_turns": total_turns_played
                }
            )
        )
    
    return new_state


def should_continue(state: GameState) -> Literal["continue", "end"]:
    """Determine if the game should continue or end."""
    return "end" if state["is_game_over"] else "continue"





def create_game_graph() -> StateGraph:
    """Create and compile the main game graph."""
    
    def get_initial_state(state: Optional[GameState]) -> GameState:
        """Provide default state if none given."""
        if state is None or (isinstance(state, dict) and not state.get("players")):
            return create_initial_game_state()
        return state
    
    # Create the graph
    graph = StateGraph(GameState)
    
    # Add initialization node to handle default state
    graph.add_node("initialize", get_initial_state)
    
    # Add game nodes
    graph.add_node("start_turn", start_turn)
    graph.add_node("get_player_decision", get_player_decision)
    graph.add_node("apply_action", apply_action)
    graph.add_node("check_game_end", check_game_end)
    
    # Add edges
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "start_turn")
    graph.add_edge("start_turn", "get_player_decision")
    graph.add_edge("get_player_decision", "apply_action")
    graph.add_edge("apply_action", "check_game_end")
    
    # Add conditional edge from check_game_end
    graph.add_conditional_edges(
        "check_game_end",
        should_continue,
        {
            "continue": "start_turn",
            "end": END
        }
    )
    
    # Compile the graph
    return graph.compile()


# Create a singleton instance of the compiled graph
game_graph = create_game_graph() 