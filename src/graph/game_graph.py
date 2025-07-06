"""Main game graph using LangGraph for turn-based game flow."""
from typing import Literal, Optional
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from src.models import GameState, ActionRecord, GameLogEntry, TurnActions, ExtractAction, ShareAction, create_initial_game_state
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
    new_state["current_turn_actions"] = None
    new_state["pending_emotion_updates"] = {}
    new_state["current_player_prompt"] = None
    
    return new_state


def get_player_decision(state: GameState) -> GameState:
    """Get the player's decisions for both extract and share actions."""
    import copy
    from src.agents.decision_agent import make_turn_decision
    
    # Create a deep copy to avoid mutation
    new_state = copy.deepcopy(state)
    
    current_player_id = new_state["current_player_id"]
    current_player = new_state["players"][current_player_id]
    
    # Use LLM for both decisions
    print(f"\n{current_player_id}'s turn:")
    decision, prompt_text = make_turn_decision(
        player_id=current_player_id,
        game_state=new_state,
        temperature=0.7
    )
    new_state["current_player_prompt"] = prompt_text
    
    # Create extract action
    extract_effects = EXTRACTION_EFFECTS[ExtractionLevel(decision.extract_level)]
    extract_action = ExtractAction(
        target_player=decision.extract_target,
        level=decision.extract_level,
        points_gained=extract_effects["points"],
        pain_caused_to=[],  # Will be filled in apply_action
        emotion_changes={},  # Will be filled in apply_action
        reasoning=decision.extract_reasoning
    )
    
    # Create share action
    share_effects = SHARE_EFFECTS[ShareLevel(decision.share_level)]
    share_action = ShareAction(
        target_player=decision.share_target,
        level=decision.share_level,
        points_gained=share_effects["points"],
        pleasure_given_to=[],  # Will be filled in apply_action
        emotion_changes={},  # Will be filled in apply_action
        reasoning=decision.share_reasoning
    )
    
    # Create turn actions
    turn_actions = TurnActions(
        turn=new_state["turn_number"],
        player_id=current_player_id,
        extract_action=extract_action,
        share_action=share_action
    )
    
    new_state["current_turn_actions"] = turn_actions
    
    # Log the decisions
    new_state["game_log"].append(
        GameLogEntry(
            turn=new_state["turn_number"],
            event_type="action",
            player_id=current_player_id,
            message=f"{current_player_id} chose extraction level {decision.extract_level} with {decision.extract_target} and sharing level {decision.share_level} with {decision.share_target}",
            details={
                "emotion": current_player["emotion"].value,
                "extract_target": decision.extract_target,
                "extract_level": decision.extract_level,
                "share_target": decision.share_target,
                "share_level": decision.share_level
            }
        )
    )
    
    return new_state


def apply_action(state: GameState) -> GameState:
    """Apply both extract and share actions, updating points and emotions."""
    import copy
    
    # Create a deep copy of the state to avoid mutation issues
    new_state = copy.deepcopy(state)
    
    turn_actions = new_state["current_turn_actions"]
    current_player_id = new_state["current_player_id"]
    adjacent_players = new_state["players"][current_player_id]["adjacent_players"]
    
    # Track total points gained this turn
    total_points = 0
    pending_updates = {}
    
    # Apply extraction effects
    extract_action = turn_actions["extract_action"]
    extract_effects = EXTRACTION_EFFECTS[ExtractionLevel(extract_action["level"])]
    total_points += extract_action["points_gained"]
    
    if extract_effects["pain_intensity"] != "none":
        # Pain affects ALL adjacent players
        pain_caused_to = adjacent_players.copy()
        extract_action["pain_caused_to"] = pain_caused_to
        
        # Apply emotion changes for intense pain (anger overrides any emotion)
        if extract_effects["causes_anger"]:
            for adj_player_id in adjacent_players:
                pending_updates[adj_player_id] = Emotion.ANGRY
                extract_action["emotion_changes"][adj_player_id] = Emotion.ANGRY
        
        # Log the extraction effects
        new_state["game_log"].append(
            GameLogEntry(
                turn=new_state["turn_number"],
                event_type="action",
                player_id=current_player_id,
                message=f"{current_player_id} extracted with {extract_action['target_player']} causing {extract_effects['pain_intensity']} pain to all adjacent players",
                details={
                    "target": extract_action["target_player"],
                    "pain_intensity": extract_effects["pain_intensity"],
                    "affected_players": pain_caused_to
                }
            )
        )
    
    # Apply share culture effects
    share_action = turn_actions["share_action"]
    share_effects = SHARE_EFFECTS[ShareLevel(share_action["level"])]
    total_points += share_action["points_gained"]
    
    if share_effects["pleasure_intensity"] != "none":
        # Pleasure affects ALL adjacent players
        pleasure_given_to = adjacent_players.copy()
        share_action["pleasure_given_to"] = pleasure_given_to
        
        # Apply emotion changes for intense pleasure (only if not already angry)
        if share_effects["causes_happiness"]:
            for adj_player_id in adjacent_players:
                # Only make happy if not being made angry this turn and currently neutral
                if adj_player_id not in pending_updates and new_state["players"][adj_player_id]["emotion"] == Emotion.NEUTRAL:
                    pending_updates[adj_player_id] = Emotion.HAPPY
                    share_action["emotion_changes"][adj_player_id] = Emotion.HAPPY
        
        # Log the share effects
        new_state["game_log"].append(
            GameLogEntry(
                turn=new_state["turn_number"],
                event_type="action",
                player_id=current_player_id,
                message=f"{current_player_id} shared culture with {share_action['target_player']} giving {share_effects['pleasure_intensity']} pleasure to all adjacent players",
                details={
                    "target": share_action["target_player"],
                    "pleasure_intensity": share_effects["pleasure_intensity"],
                    "affected_players": pleasure_given_to
                }
            )
        )
    
    # Update current player's points
    new_state["players"][current_player_id]["points"] += total_points
    
    # Add turn actions to player's history
    new_state["players"][current_player_id]["turn_history"].append(turn_actions)
    
    # Also update old-style action_history for compatibility
    # Add extract action
    new_state["players"][current_player_id]["action_history"].append(
        ActionRecord(
            turn=turn_actions["turn"],
            player_id=current_player_id,
            action_type=ActionType.EXTRACT,
            level=extract_action["level"],
            points_gained=extract_action["points_gained"],
            pain_caused_to=extract_action["pain_caused_to"],
            pleasure_given_to=[],
            emotion_changes=extract_action["emotion_changes"],
            reasoning=extract_action["reasoning"]
        )
    )
    
    # Add share action
    new_state["players"][current_player_id]["action_history"].append(
        ActionRecord(
            turn=turn_actions["turn"],
            player_id=current_player_id,
            action_type=ActionType.SHARE,
            level=share_action["level"],
            points_gained=share_action["points_gained"],
            pain_caused_to=[],
            pleasure_given_to=share_action["pleasure_given_to"],
            emotion_changes=share_action["emotion_changes"],
            reasoning=share_action["reasoning"]
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