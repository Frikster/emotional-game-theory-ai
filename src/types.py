"""Type definitions and constants for the game."""
from enum import Enum


class Emotion(str, Enum):
    """Possible emotional states for players."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    ANGRY = "angry"


class ExtractionLevel(int, Enum):
    """Resource extraction levels with their point values."""
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


class PainIntensity(str, Enum):
    """Pain intensity levels caused by extraction actions."""
    NONE = "none"
    MILD = "mild"
    INTENSE = "intense"


# Game constants
MAX_TURNS = 5
TOTAL_PLAYERS = 3

# Adjacency mapping for 3 players in a triangle
ADJACENCY_MAP = {
    "Player1": ["Player2", "Player3"],
    "Player2": ["Player1", "Player3"],
    "Player3": ["Player1", "Player2"],
}

# Extraction effects mapping
EXTRACTION_EFFECTS = {
    ExtractionLevel.LEVEL_1: {
        "points": 1,
        "pain_intensity": PainIntensity.NONE,
        "causes_anger": False,
    },
    ExtractionLevel.LEVEL_2: {
        "points": 2,
        "pain_intensity": PainIntensity.MILD,
        "causes_anger": False,
    },
    ExtractionLevel.LEVEL_3: {
        "points": 3,
        "pain_intensity": PainIntensity.INTENSE,
        "causes_anger": True,
    },
} 