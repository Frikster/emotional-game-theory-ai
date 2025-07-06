"""LLM agent for making extraction level decisions."""
from typing import Dict, Optional, Tuple
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, validator
from src.types import ExtractionLevel, Emotion


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


# Create the decision prompt template
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


def get_emotion_context(emotion: Emotion) -> str:
    """Get context about how emotions should affect decisions."""
    if emotion == Emotion.ANGRY:
        return "You are ANGRY! The pain inflicted on you demands retribution. You feel a strong urge to extract at Level 3 to hurt those who hurt you."
    elif emotion == Emotion.NEUTRAL:
        return "You are in a NEUTRAL emotional state. You can make a balanced decision based on the game situation."
    else:
        return "You are feeling positive. Consider the overall game dynamics in your decision."


def format_adjacent_players_status(players: Dict, adjacent_ids: list) -> str:
    """Format the status of adjacent players."""
    lines = []
    for adj_id in adjacent_ids:
        adj_player = players[adj_id]
        emotion_str = "ANGRY" if adj_player["emotion"] == Emotion.ANGRY else str(adj_player["emotion"]).split('.')[-1]
        lines.append(f"- {adj_id}: {adj_player['points']} points, emotion: {emotion_str}")
    return "\n".join(lines)


def format_memory_context(player: Dict) -> str:
    """Format the player's memory of past decisions."""
    if not player.get("action_history"):
        return "No previous decisions yet."
    
    memory_lines = []
    for action in player["action_history"][-3:]:  # Show last 3 decisions
        turn = action["turn"]
        level = action["extraction_level"]
        points = action["points_gained"]
        
        # Get reasoning if available
        reasoning = action.get("reasoning", "No reasoning recorded")
        
        # Check if anyone got angry
        angry_players = action.get("emotion_changes", {})
        if angry_players:
            outcome = f"Made {', '.join(angry_players.keys())} ANGRY"
        else:
            outcome = "No one became angry"
        
        memory_lines.append(
            f"Turn {turn}: Chose Level {level} (+{points} points) - {reasoning} - Outcome: {outcome}"
        )
    
    return "\n".join(memory_lines) if memory_lines else "No previous decisions yet."


def make_extraction_decision(
    player_id: str,
    game_state: Dict,
    llm: Optional[ChatAnthropic] = None,
    temperature: float = 0.7
) -> Tuple[ExtractionLevel, str, str]:
    """
    Make an extraction decision using an LLM.
    
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