"""Data models for the game state using TypedDict for LangGraph."""
from typing import TypedDict, Dict, List, Optional, Literal, Union
from src.types import Emotion, ExtractionLevel, ShareLevel, ActionType


class ExtractAction(TypedDict):
    """Record of an extraction action."""
    target_player: str  # Which adjacent player was selected for extraction
    level: int  # 1-3
    points_gained: int
    pain_caused_to: List[str]  # All adjacent players affected
    emotion_changes: Dict[str, Emotion]  # player_id -> new emotion
    reasoning: str


class ShareAction(TypedDict):
    """Record of a share culture action."""
    target_player: str  # Which adjacent player was selected for sharing
    level: int  # 1-3
    points_gained: int
    pleasure_given_to: List[str]  # All adjacent players affected
    emotion_changes: Dict[str, Emotion]  # player_id -> new emotion
    reasoning: str


class TurnActions(TypedDict):
    """All actions taken in a single turn."""
    turn: int
    player_id: str
    extract_action: ExtractAction
    share_action: ShareAction


# Keep old ActionRecord for backward compatibility during transition
class ActionRecord(TypedDict):
    """Record of a single action taken by a player."""
    turn: int
    player_id: str
    action_type: ActionType  # "extract" or "share"
    level: Union[ExtractionLevel, ShareLevel]  # Level 1-3
    points_gained: int
    # Effects on other players
    pain_caused_to: List[str]  # For extraction actions
    pleasure_given_to: List[str]  # For share actions
    emotion_changes: Dict[str, Emotion]  # player_id -> new emotion
    reasoning: str  # Agent's reasoning for this decision


class PlayerMemory(TypedDict):
    """Memory entry for a player's past decision."""
    turn: int
    action_type: str  # "extract" or "share"
    level: int  # 1-3
    reasoning: str
    outcome: str  # What happened as a result


class PlayerInfo(TypedDict):
    """Information about a single player."""
    id: str
    points: int
    emotion: Emotion
    adjacent_players: List[str]
    action_history: List[ActionRecord]  # Will transition to turn_history
    turn_history: List[TurnActions]  # New: both actions per turn
    memory: List[PlayerMemory]  # Agent's working memory
    system_prompt: str  # Custom prompt for this agent


class GameLogEntry(TypedDict):
    """Entry in the game log for tracking events."""
    turn: int
    event_type: Literal["action", "emotion_change", "game_start", "game_end"]
    player_id: Optional[str]
    message: str
    details: Dict[str, any]


class GameState(TypedDict):
    """Main game state for LangGraph."""
    # Core game state
    players: Dict[str, PlayerInfo]
    current_player_id: Optional[str]
    turn_number: int
    
    # Game flow
    is_game_over: bool
    
    # History and logging
    game_log: List[GameLogEntry]
    
    # Current turn state
    current_action: Optional[ActionRecord]  # Will transition to current_turn_actions
    current_turn_actions: Optional[TurnActions]  # New: both actions for current turn
    pending_emotion_updates: Dict[str, Emotion]  # player_id -> new emotion
    current_player_prompt: Optional[str]  # The prompt shown to the current player


def create_initial_game_state() -> GameState:
    """Create the initial game state with 3 players."""
    from src.types import ADJACENCY_MAP
    
    players = {}
    for player_id in ["Player1", "Player2", "Player3"]:
        players[player_id] = PlayerInfo(
            id=player_id,
            points=0,
            emotion=Emotion.NEUTRAL,
            adjacent_players=ADJACENCY_MAP[player_id],
            action_history=[],
            turn_history=[],
            memory=[],
            system_prompt=""
        )
    
    return GameState(
        players=players,
        current_player_id=None,
        turn_number=0,
        is_game_over=False,
        game_log=[
            GameLogEntry(
                turn=0,
                event_type="game_start",
                player_id=None,
                message="Game started with 3 players",
                details={"player_ids": list(players.keys())}
            )
        ],
        current_action=None,
        current_turn_actions=None,
        pending_emotion_updates={},
        current_player_prompt=None
    ) 