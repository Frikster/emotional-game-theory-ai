# Emotional Game Theory AI

A LangGraph-based multi-agent game simulation exploring emotional dynamics in cooperative/competitive scenarios.

## Overview

This project implements an iterated game where LLM agents can extract resources at different levels, with higher extraction levels causing "pain" to adjacent players and triggering emotional state changes. The project explores how emotions affect strategic decision-making in multi-agent environments.

## Setup Instructions

### Prerequisites

- Python 3.11+
- `uv` package manager ([install instructions](https://github.com/astral-sh/uv))
- OpenAI API key (or other LLM provider)

### Installation

1. Clone the repository:
```bash
git clone <repo-url>
cd emotional-game-theory-ai
```

2. Create and activate the virtual environment (already done if using uv):
```bash
uv sync
```

3. Set up environment variables:
Create a `.env` file in the project root with:
```
OPENAI_API_KEY=your-api-key-here
```

### Project Structure

```
emotional-game-theory-ai/
├── src/                    # Main source code
│   ├── graph/             # LangGraph definitions
│   ├── agents/            # LLM agent implementations
│   └── game_logic/        # Game mechanics and rules
├── config/                # Configuration files
├── tests/                 # Test files
└── README.md             # This file
```

## Running the Game

```bash
python main.py
```

This will run a basic 5-turn game with 3 agents making extraction decisions.

## Development

The project is structured around LangGraph for state management and turn orchestration. Key components:

- **GameState**: Tracks all players, turns, and history
- **Nodes**: Discrete game phases (decision, action, update)
- **Agents**: LLM-powered decision makers with emotional states

## Current Features

- Basic turn-based gameplay
- Resource extraction with 3 levels
- Emotional state tracking (neutral/happy/angry)
- Pain/pleasure mechanics affecting adjacent players
