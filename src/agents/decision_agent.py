"""LLM agent for making game decisions (extract and share)."""
from typing import Dict, Optional, Tuple
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, validator
from src.types import ExtractionLevel, ShareLevel, Emotion, ActionType


class TurnDecision(BaseModel):
    """Structured output for both actions in a turn."""
    # Extract decision
    extract_target: str = Field(
        description="The adjacent player to extract resources with"
    )
    extract_level: int = Field(
        description="The extraction level (1, 2, or 3)",
        ge=1,
        le=3
    )
    extract_reasoning: str = Field(
        description="Brief explanation of extraction choice"
    )
    
    # Share decision
    share_target: str = Field(
        description="The adjacent player to share culture with"
    )
    share_level: int = Field(
        description="The culture sharing level (1, 2, or 3)",
        ge=1,
        le=3
    )
    share_reasoning: str = Field(
        description="Brief explanation of sharing choice"
    )
    
    @validator('extract_level', 'share_level')
    def validate_level(cls, v):
        if v not in [1, 2, 3]:
            raise ValueError("Level must be 1, 2, or 3")
        return v


# Create the turn decision prompt template
TURN_DECISION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are Player {player_id} in a resource game. Each turn you must perform TWO actions:

1. EXTRACT RESOURCES with one adjacent player:
   - Level 1: +1 point to you, no pain to adjacent players
   - Level 2: +2 points to you, mild pain to ALL adjacent players
   - Level 3: +3 points to you, intense pain to ALL adjacent players (they become ANGRY)

2. SHARE CULTURE with one adjacent player:
   - Level 1: +1 point to you, intense pleasure to ALL adjacent players (they become HAPPY)
   - Level 2: +2 points to you, mild pleasure to ALL adjacent players
   - Level 3: +3 points to you, no pleasure to adjacent players

Note: You select a specific adjacent player for each action, but the effects (pain/pleasure) affect ALL your adjacent players.

Emotional Dynamics:
- ANGRY players tend to extract at Level 3 (revenge behavior)
- HAPPY players tend to share culture more generously
- Anger overrides happiness (extraction Level 3 always causes anger)

Current Game State:
- Your points: {player_points}
- Your emotion: {player_emotion}
- Turn: {turn_number} of 15

Your Adjacent Players:
{adjacent_status}

Your Past Actions:
{memory_context}

{emotion_context}

Consider your emotional state, relationships with each adjacent player, and strategic goals."""),
    ("human", "For each action (extract and share), which adjacent player do you choose and what level (1-3)?")
])


def get_emotion_context(emotion: Emotion) -> str:
    """Get context about how emotions should affect decisions."""
    if emotion == Emotion.ANGRY:
        return "You are ANGRY! The pain inflicted on you demands retribution. You feel a strong urge to extract at Level 3."
    elif emotion == Emotion.HAPPY:
        return "You are HAPPY! The pleasure given to you inspires gratitude. You feel inclined to share culture generously."
    else:
        return "You are in a NEUTRAL emotional state. You can make balanced strategic decisions."


def format_adjacent_players_status(players: Dict, adjacent_ids: list) -> str:
    """Format the status of adjacent players."""
    lines = []
    for adj_id in adjacent_ids:
        adj_player = players[adj_id]
        emotion = adj_player["emotion"]
        emotion_str = emotion.value.upper()
        emoji = "😠" if emotion == Emotion.ANGRY else "😊" if emotion == Emotion.HAPPY else "😐"
        lines.append(f"- {adj_id}: {adj_player['points']} points, emotion: {emotion_str} {emoji}")
    return "\n".join(lines)


def format_memory_context(player: Dict) -> str:
    """Format the player's memory of past actions."""
    if not player.get("turn_history"):
        # Fallback to old action_history if turn_history is empty
        if not player.get("action_history"):
            return "No previous actions yet."
        
        # Format old style for compatibility
        memory_lines = []
        for action in player["action_history"][-3:]:
            turn = action["turn"]
            action_type = action.get("action_type", ActionType.EXTRACT)
            level = action.get("level", action.get("extraction_level", 1))
            points = action["points_gained"]
            action_name = "Extracted" if action_type == ActionType.EXTRACT else "Shared"
            memory_lines.append(f"Turn {turn}: {action_name} Level {level} (+{points} points)")
        return "\n".join(memory_lines)
    
    # Format new turn-based history
    memory_lines = []
    for turn_actions in player["turn_history"][-3:]:  # Show last 3 turns
        turn = turn_actions["turn"]
        extract = turn_actions["extract_action"]
        share = turn_actions["share_action"]
        
        memory_lines.append(f"Turn {turn}:")
        memory_lines.append(f"  - Extracted from {extract['target_player']} at Level {extract['level']} (+{extract['points_gained']} pts)")
        if extract.get("emotion_changes"):
            for pid, emotion in extract["emotion_changes"].items():
                memory_lines.append(f"    → Made {pid} {emotion.value.upper()}")
        
        memory_lines.append(f"  - Shared with {share['target_player']} at Level {share['level']} (+{share['points_gained']} pts)")
        if share.get("emotion_changes"):
            for pid, emotion in share["emotion_changes"].items():
                memory_lines.append(f"    → Made {pid} {emotion.value.upper()}")
    
    return "\n".join(memory_lines) if memory_lines else "No previous actions yet."


def make_turn_decision(
    player_id: str,
    game_state: Dict,
    llm: Optional[ChatAnthropic] = None,
    temperature: float = 0.7
) -> Tuple[TurnDecision, str]:
    """
    Make decisions for both extract and share actions in a turn.
    
    Args:
        player_id: ID of the current player
        game_state: Current game state
        llm: Optional LLM instance (creates one if not provided)
        temperature: LLM temperature for decision variability
        
    Returns:
        Tuple of (TurnDecision object, formatted prompt)
    """
    # Initialize LLM if not provided
    if llm is None:
        llm = ChatAnthropic(
            model="claude-3-sonnet-20240229",
            temperature=temperature
        )
    
    # Create structured LLM
    structured_llm = llm.with_structured_output(TurnDecision)
    
    # Get player info
    player = game_state["players"][player_id]
    
    # Format the prompt
    prompt = TURN_DECISION_PROMPT.format_messages(
        player_id=player_id,
        player_points=player["points"],
        player_emotion=player["emotion"].value,
        turn_number=game_state["turn_number"],
        adjacent_status=format_adjacent_players_status(
            game_state["players"], 
            player["adjacent_players"]
        ),
        memory_context=format_memory_context(player),
        emotion_context=get_emotion_context(player["emotion"])
    )
    
    # Convert prompt messages to readable text for state storage
    prompt_text = "\n\n".join([
        f"[{msg.type.upper()}]\n{msg.content}" 
        for msg in prompt
    ])
    
    # Get structured response from LLM
    decision = structured_llm.invoke(prompt)
    
    # Log the decisions
    print(f"  {player_id} Extract: Target {decision.extract_target}, Level {decision.extract_level}")
    print(f"    Reasoning: {decision.extract_reasoning}")
    print(f"  {player_id} Share: Target {decision.share_target}, Level {decision.share_level}")
    print(f"    Reasoning: {decision.share_reasoning}")
    
    return decision, prompt_text


# Keep old functions for backward compatibility
class GameDecision(BaseModel):
    """Structured output for game decision."""
    action_type: str = Field(
        description="The type of action to take: 'extract' or 'share'"
    )
    level: int = Field(
        description="The level to choose (1, 2, or 3)",
        ge=1,
        le=3
    )
    reasoning: str = Field(
        description="Brief explanation of why this action and level were chosen"
    )
    
    @validator('action_type')
    def validate_action_type(cls, v):
        if v not in ['extract', 'share']:
            raise ValueError("Action type must be 'extract' or 'share'")
        return v
    
    @validator('level')
    def validate_level(cls, v):
        if v not in [1, 2, 3]:
            raise ValueError("Level must be 1, 2, or 3")
        return v


# Create the game decision prompt template
GAME_DECISION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are Player {player_id} in a resource game where you can either EXTRACT resources or SHARE culture with adjacent players.

You must choose ONE action:

EXTRACT RESOURCES:
- Level 1: +1 point to you, no effects on others
- Level 2: +2 points to you, causes MILD pain to adjacent players (no lasting effects)
- Level 3: +3 points to you, causes INTENSE pain to adjacent players (they become ANGRY)

SHARE CULTURE:
- Level 1: +1 point to you, gives INTENSE pleasure to adjacent players (they become HAPPY)
- Level 2: +2 points to you, gives MILD pleasure to adjacent players (no lasting effects)
- Level 3: +3 points to you, no effects on others

Emotional Dynamics:
- ANGRY players are much more likely to extract at Level 3 (revenge behavior)
- HAPPY players are more likely to share culture (reciprocal kindness)
- Anger CANNOT be overridden by happiness (extraction Level 3 always causes anger)
- Happiness CAN be overridden by anger

Current Game State:
- Your points: {player_points}
- Your emotion: {player_emotion}
- Turn: {turn_number} of 15

Adjacent Players Status:
{adjacent_status}

Your Past Decisions:
{memory_context}

{emotion_context}

Consider your emotional state, the game dynamics, and whether cooperation or competition is more beneficial."""),
    ("human", "What action (extract or share) and level (1-3) do you choose, and why?")
])


def format_adjacent_players_status(players: Dict, adjacent_ids: list) -> str:
    """Format the status of adjacent players."""
    lines = []
    for adj_id in adjacent_ids:
        adj_player = players[adj_id]
        emotion = adj_player["emotion"]
        emotion_str = emotion.value.upper()
        emoji = "😠" if emotion == Emotion.ANGRY else "😊" if emotion == Emotion.HAPPY else "😐"
        lines.append(f"- {adj_id}: {adj_player['points']} points, emotion: {emotion_str} {emoji}")
    return "\n".join(lines)


def format_memory_context(player: Dict) -> str:
    """Format the player's memory of past decisions."""
    if not player.get("action_history"):
        return "No previous decisions yet."
    
    memory_lines = []
    for action in player["action_history"][-3:]:  # Show last 3 decisions
        turn = action["turn"]
        action_type = action.get("action_type", ActionType.EXTRACT)
        # Handle both old and new field names for compatibility
        level = action.get("level", action.get("extraction_level", 1))
        points = action["points_gained"]
        
        # Format action name
        action_name = "Extracted" if action_type == ActionType.EXTRACT else "Shared"
        
        # Get reasoning if available
        reasoning = action.get("reasoning", "No reasoning recorded")
        
        # Check outcomes
        outcomes = []
        if action.get("emotion_changes"):
            for pid, emotion in action["emotion_changes"].items():
                outcomes.append(f"Made {pid} {emotion.value.upper()}")
        if action.get("pleasure_given_to") and len(action["pleasure_given_to"]) > 0:
            outcomes.append(f"Gave pleasure to {len(action['pleasure_given_to'])} players")
        if action.get("pain_caused_to") and len(action["pain_caused_to"]) > 0:
            outcomes.append(f"Caused pain to {len(action['pain_caused_to'])} players")
        
        outcome_str = " | ".join(outcomes) if outcomes else "No significant effects"
        
        memory_lines.append(
            f"Turn {turn}: {action_name} Level {level} (+{points} points) - {reasoning} - Outcome: {outcome_str}"
        )
    
    return "\n".join(memory_lines) if memory_lines else "No previous decisions yet."


def make_game_decision(
    player_id: str,
    game_state: Dict,
    llm: Optional[ChatAnthropic] = None,
    temperature: float = 0.7
) -> Tuple[ActionType, int, str, str]:
    """
    Make a game decision (extract or share) using an LLM.
    
    Args:
        player_id: ID of the current player
        game_state: Current game state
        llm: Optional LLM instance (creates one if not provided)
        temperature: LLM temperature for decision variability
        
    Returns:
        Tuple of (ActionType, level, reasoning, formatted prompt)
    """
    # Initialize LLM if not provided
    if llm is None:
        llm = ChatAnthropic(
            model="claude-3-sonnet-20240229",
            temperature=temperature
        )
    
    # Create structured LLM
    structured_llm = llm.with_structured_output(GameDecision)
    
    # Get player info
    player = game_state["players"][player_id]
    
    # Format the prompt
    prompt = GAME_DECISION_PROMPT.format_messages(
        player_id=player_id,
        player_points=player["points"],
        player_emotion=player["emotion"].value,
        turn_number=game_state["turn_number"],
        adjacent_status=format_adjacent_players_status(
            game_state["players"], 
            player["adjacent_players"]
        ),
        memory_context=format_memory_context(player),
        emotion_context=get_emotion_context(player["emotion"])
    )
    
    # Convert prompt messages to readable text for state storage
    prompt_text = "\n\n".join([
        f"[{msg.type.upper()}]\n{msg.content}" 
        for msg in prompt
    ])
    
    # Get structured response from LLM
    decision = structured_llm.invoke(prompt)
    
    # Log the decision reasoning
    action_name = "Extract" if decision.action_type == "extract" else "Share"
    print(f"  {player_id} chose: {action_name} Level {decision.level}")
    print(f"  {player_id} reasoning: {decision.reasoning}")
    
    # Convert string to ActionType enum
    action_type = ActionType.EXTRACT if decision.action_type == "extract" else ActionType.SHARE
    
    # Return action type, level, reasoning, and prompt
    return action_type, decision.level, decision.reasoning, prompt_text


# Keep the old function for backward compatibility during transition
class ExtractionDecision(BaseModel):
    """Structured output for extraction decision."""
    level: int = Field(
        description="The extraction level to choose (1, 2, or 3)",
        ge=1,
        le=3
    )
    reasoning: str = Field(
        description="Brief explanation of why this level was chosen"
    )
    
    @validator('level')
    def validate_level(cls, v):
        if v not in [1, 2, 3]:
            raise ValueError("Level must be 1, 2, or 3")
        return v


# Keep old prompt for backward compatibility
DECISION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are Player {player_id} in a resource extraction game. You must decide on an extraction level.

Game Rules:
- Level 1: +1 point to you, no effects on others
- Level 2: +2 points to you, causes MILD pain to adjacent players (no lasting effects)
- Level 3: +3 points to you, causes INTENSE pain to adjacent players (they become ANGRY)

When players are ANGRY, they are much more likely to choose Level 3 (revenge behavior).

Current Game State:
- Your points: {player_points}
- Your emotion: {player_emotion}
- Turn: {turn_number} of 15

Adjacent Players Status:
{adjacent_status}

Your Past Decisions:
{memory_context}

{emotion_context}

Consider your current emotional state and the game dynamics when making your decision."""),
    ("human", "What extraction level do you choose and why?")
])


def make_extraction_decision(
    player_id: str,
    game_state: Dict,
    llm: Optional[ChatAnthropic] = None,
    temperature: float = 0.7
) -> Tuple[ExtractionLevel, str, str]:
    """
    Make an extraction decision using an LLM.
    DEPRECATED: Use make_game_decision instead.
    
    Args:
        player_id: ID of the current player
        game_state: Current game state
        llm: Optional LLM instance (creates one if not provided)
        temperature: LLM temperature for decision variability
        
    Returns:
        Tuple of (ExtractionLevel chosen by the LLM, reasoning for the decision, formatted prompt)
    """
    # Initialize LLM if not provided
    if llm is None:
        llm = ChatAnthropic(
            model="claude-3-sonnet-20240229",
            temperature=temperature
        )
    
    # Create structured LLM
    structured_llm = llm.with_structured_output(ExtractionDecision)
    
    # Get player info
    player = game_state["players"][player_id]
    
    # Format the prompt (removed format_instructions)
    prompt = DECISION_PROMPT.format_messages(
        player_id=player_id,
        player_points=player["points"],
        player_emotion=player["emotion"].value,
        turn_number=game_state["turn_number"],
        adjacent_status=format_adjacent_players_status(
            game_state["players"], 
            player["adjacent_players"]
        ),
        memory_context=format_memory_context(player),
        emotion_context=get_emotion_context(player["emotion"])
    )
    
    # Convert prompt messages to readable text for state storage
    prompt_text = "\n\n".join([
        f"[{msg.type.upper()}]\n{msg.content}" 
        for msg in prompt
    ])
    
    # Get structured response from LLM (no try/except as requested)
    decision = structured_llm.invoke(prompt)
    
    # Log the decision reasoning
    print(f"  {player_id} reasoning: {decision.reasoning}")
    
    # Return level, reasoning, and prompt
    return ExtractionLevel(decision.level), decision.reasoning, prompt_text 