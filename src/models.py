"""Data models for the game state using TypedDict for LangGraph."""
from typing import TypedDict, Dict, List, Optional, Literal
from src.types import Emotion, ExtractionLevel


class ActionRecord(TypedDict):
    """Record of a single action taken by a player."""
    turn: int
    player_id: str
    extraction_level: ExtractionLevel
    points_gained: int
    pain_caused_to: List[str]  # List of player IDs who received pain
    emotion_changes: Dict[str, str]  # player_id -> new emotion


class PlayerInfo(TypedDict):
    """Information about a single player."""
    id: str
    points: int
    emotion: Emotion
    adjacent_players: List[str]
    action_history: List[ActionRecord]


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
    current_action: Optional[ActionRecord]
    pending_emotion_updates: Dict[str, Emotion]  # player_id -> new emotion


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
            action_history=[]
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
        pending_emotion_updates={}
    ) 