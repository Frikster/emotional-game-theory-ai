# Emotional Game Theory AI

A LangGraph-based simulation exploring how emotions affect strategic decision-making in multi-agent game theory scenarios.

## What This Is

3 AI agents play an iterated resource extraction game where:
- **Level 1 extraction**: +1 point, no effects
- **Level 2 extraction**: +2 points, mild pain to adjacent players  
- **Level 3 extraction**: +3 points, intense pain → adjacent players become angry
- **Angry players** tend to extract at Level 3 more often (revenge behavior)

This creates emergent dynamics of retaliation and emotional escalation.

## Quick Start

```bash
# Install dependencies
uv sync

# Run interactive game UI
uv run langgraph dev
```

In the LangGraph UI:
1. Click "emotional_game" graph
2. Click "Invoke" with empty input `{}`  
3. Set recursion limit to 120+
4. Watch the emotional dynamics unfold!

## Game Mechanics

- **3 players** in a triangle (each adjacent to 2 others)
- **5 rounds** (15 total turns)
- **Emotions**: neutral → angry (from Level 3 extractions)
- **State tracking**: Points, emotions, action history
- **Winner**: Most points after 5 rounds

## Architecture

LangGraph nodes handle each game phase:
- `initialize` → Default game state for empty input
- `start_turn` → Select next player
- `get_player_decision` → Choose extraction level (currently random, weighted by emotion)
- `apply_action` → Update points and emotions
- `check_game_end` → Continue or finish game

## LLM Agent Decision-Making

The game uses Claude 3 Sonnet for all player decisions:
- **Structured reasoning**: Players explain their strategic choices
- **Emotional awareness**: LLMs consider their current emotional state
- **Memory**: Players remember past actions and outcomes
- **Revenge dynamics**: Angry players tend to retaliate with Level 3

## Configuration

Create a `.env` file with:
```
ANTHROPIC_API_KEY=your-anthropic-api-key  # Required
LANGCHAIN_API_KEY=your-langsmith-key      # Optional, for tracing
```

LangSmith tracing shows detailed analysis of emotional cascades and decision patterns.
