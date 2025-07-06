"""Main game graph using LangGraph for turn-based game flow."""
from typing import Literal, Optional
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from src.models import GameState, ActionRecord, GameLogEntry, create_initial_game_state
from src.types import MAX_TURNS, Emotion, EXTRACTION_EFFECTS, SHARE_EFFECTS, ActionType, ExtractionLevel, ShareLevel


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
    new_state["current_player_prompt"] = None
    
    return new_state


def get_player_decision(state: GameState) -> GameState:
    """Get the player's action decision using LLM."""
    import copy
    from src.agents.decision_agent import make_extraction_decision
    
    # Create a deep copy to avoid mutation
    new_state = copy.deepcopy(state)
    
    current_player_id = new_state["current_player_id"]
    current_player = new_state["players"][current_player_id]
    
    # Use LLM for decision
    print(f"\n{current_player_id}'s turn:")
    # TODO: In Step 3, we'll update this to support both extract and share
    # For now, we'll only do extraction to keep the game working
    extraction_level, reasoning, prompt_text = make_extraction_decision(
        player_id=current_player_id,
        game_state=new_state,
        temperature=0.7
    )
    new_state["current_player_prompt"] = prompt_text
    
    # For now, always use EXTRACT action type until Step 3
    action_type = ActionType.EXTRACT
    level = extraction_level.value
    
    # Log the decision
    action_name = "extraction" if action_type == ActionType.EXTRACT else "culture sharing"
    new_state["game_log"].append(
        GameLogEntry(
            turn=new_state["turn_number"],
            event_type="action",
            player_id=current_player_id,
            message=f"{current_player_id} chose {action_name} level {level}",
            details={
                "emotion": current_player["emotion"].value,
                "action_type": action_type.value,
                "level": level
            }
        )
    )
    
    # Get effects based on action type
    if action_type == ActionType.EXTRACT:
        effects = EXTRACTION_EFFECTS[ExtractionLevel(level)]
        points = effects["points"]
    else:  # SHARE
        effects = SHARE_EFFECTS[ShareLevel(level)]
        points = effects["points"]
    
    # Create action record (to be processed in apply_action)
    action = ActionRecord(
        turn=new_state["turn_number"],
        player_id=current_player_id,
        action_type=action_type,
        level=level,
        points_gained=points,
        pain_caused_to=[],  # Will be filled in apply_action
        pleasure_given_to=[],  # Will be filled in apply_action
        emotion_changes={},   # Will be filled in apply_action
        reasoning=reasoning
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
    
    # Get adjacent players
    adjacent_players = new_state["players"][current_player_id]["adjacent_players"]
    pending_updates = {}
    
    # Apply effects based on action type
    if action["action_type"] == ActionType.EXTRACT:
        # Handle extraction effects
        effects = EXTRACTION_EFFECTS[ExtractionLevel(action["level"])]
        pain_caused_to = []
        
        if effects["pain_intensity"] != "none":
            for adj_player_id in adjacent_players:
                pain_caused_to.append(adj_player_id)
                
                # Apply emotion changes for intense pain (anger overrides any emotion)
                if effects["causes_anger"]:
                    pending_updates[adj_player_id] = Emotion.ANGRY
                    action["emotion_changes"][adj_player_id] = Emotion.ANGRY
        
        action["pain_caused_to"] = pain_caused_to
        
        # Log the extraction effects
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
    
    else:  # SHARE action
        # Handle share culture effects
        effects = SHARE_EFFECTS[ShareLevel(action["level"])]
        pleasure_given_to = []
        
        if effects["pleasure_intensity"] != "none":
            for adj_player_id in adjacent_players:
                pleasure_given_to.append(adj_player_id)
                
                # Apply emotion changes for intense pleasure (only if not angry)
                if effects["causes_happiness"]:
                    # Only make happy if currently neutral (anger is not overridden by happiness)
                    if new_state["players"][adj_player_id]["emotion"] == Emotion.NEUTRAL:
                        pending_updates[adj_player_id] = Emotion.HAPPY
                        action["emotion_changes"][adj_player_id] = Emotion.HAPPY
        
        action["pleasure_given_to"] = pleasure_given_to
        
        # Log the share effects
        if pleasure_given_to:
            new_state["game_log"].append(
                GameLogEntry(
                    turn=new_state["turn_number"],
                    event_type="action",
                    player_id=current_player_id,
                    message=f"{current_player_id} gave {effects['pleasure_intensity']} pleasure to {', '.join(pleasure_given_to)}",
                    details={
                        "pleasure_intensity": effects["pleasure_intensity"],
                        "affected_players": pleasure_given_to
                    }
                )
            )
    
    # Add action to current player's history
    new_state["players"][current_player_id]["action_history"].append(action)
    
    # Apply pending emotion updates
    for player_id, new_emotion in pending_updates.items():
        old_emotion = new_state["players"][player_id]["emotion"]
        new_state["players"][player_id]["emotion"] = new_emotion
        
        new_state["game_log"].append(
            GameLogEntry(
                turn=new_state["turn_number"],
                event_type="emotion_change",
                player_id=player_id,
                message=f"{player_id}'s emotion changed from {old_emotion.value} to {new_emotion.value}",
                details={
                    "old_emotion": old_emotion.value,
                    "new_emotion": new_emotion.value,
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