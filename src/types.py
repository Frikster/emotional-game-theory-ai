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


class ShareLevel(int, Enum):
    """Culture sharing levels with their point values."""
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


class PainIntensity(str, Enum):
    """Pain intensity levels caused by extraction actions."""
    NONE = "none"
    MILD = "mild"
    INTENSE = "intense"


class PleasureIntensity(str, Enum):
    """Pleasure intensity levels caused by sharing actions."""
    NONE = "none"
    MILD = "mild"
    INTENSE = "intense"


class ActionType(str, Enum):
    """Types of actions players can take."""
    EXTRACT = "extract"
    SHARE = "share"


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

# Share culture effects mapping (inverse of extraction)
SHARE_EFFECTS = {
    ShareLevel.LEVEL_1: {
        "points": 1,
        "pleasure_intensity": PleasureIntensity.INTENSE,
        "causes_happiness": True,  # Makes adjacent players HAPPY
    },
    ShareLevel.LEVEL_2: {
        "points": 2,
        "pleasure_intensity": PleasureIntensity.MILD,
        "causes_happiness": False,  # Mild pleasure, no emotion change
    },
    ShareLevel.LEVEL_3: {
        "points": 3,
        "pleasure_intensity": PleasureIntensity.NONE,
        "causes_happiness": False,  # No pleasure given
    },
} 