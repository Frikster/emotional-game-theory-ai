```
---
title: Hume.ai Voice Chat
emoji: 🎤
colorFrom: blue
colorTo: purple
sdk: streamlit
sdk_version: 1.27.2
app_file: app.py
pinned: false
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

# emotional-game-theory-ai
Emotional Game Theory AI

# AI Safety Game Theory Experiment

An experimental application exploring how emotional data impacts AI decision-making in game-theoretic scenarios. (WIP)

## Screenshots

![Game Configuration](screenshots/config.png)
*Initial game configuration screen where you can select the game type, emotion, and other parameters*

![Conversation Interface](screenshots/chat.png)
*Voice chat interface showing the conversation with emotion detection*

![Decision Phase](screenshots/choice.png)
*Decision phase where players make their game theory choices*

![Results Display](screenshots/results.png)
*Results screen showing the outcome of each round*


## Setup

1. Install dependencies:
`uv sync`
`source .venv/bin/activate && uv pip install "hume[microphone]"` 

2. Run locally
`uv run streamlit run app.py`
