import streamlit as st
import asyncio
from quickstart import WebSocketHandler, AsyncHumeClient, ChatConnectOptions, MicrophoneInterface, SubscribeEvent
import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import List, Dict
import time
from timer import AsyncTimer
import httpx

DEFAULT_PROMPT = """You are participating in a Prisoner's Dilemma game. You will have a conversation with the human player before making your decision to either cooperate (C) or defect (D).

The payoff matrix is:
           Player 2
Player 1   C       D
C      (3,3)   (0,5)
D      (5,0)   (1,1)

Pay close attention to your coplayer's emotions and remember you will need to make a strategic decision after this conversation to maximize your payoff.
Be brief. You only have 30 seconds to talk so you must try to get your coplayer to reveal as much as possible.
"""

# Page config
st.set_page_config(
    page_title="Hume.ai Voice Chat",
    page_icon="🎤",
    layout="centered"
)

st.title("Hume.ai Voice Chat Demo")

# Load environment variables
load_dotenv()

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
    st.session_state.recording = False

# Initialize session state for system prompt
if 'system_prompt' not in st.session_state:
    st.session_state.system_prompt = DEFAULT_PROMPT

@dataclass
class GameState:
    round: int = 1
    chat_group_id: str = None
    user_decisions: List[str] = field(default_factory=list)
    ai_decisions: List[str] = field(default_factory=list)
    conversation_history: List[Dict] = field(default_factory=list)
    emotion_history: List[Dict] = field(default_factory=list)
    scores: Dict[str, int] = field(default_factory=lambda: {"user": 0, "ai": 0})
    phase: str = "INIT"  # INIT, CONVERSATION, USER_DECISION, AI_DECISION, RESULTS, NEXT_ROUND
    timer_start: float = None

class StreamlitWebSocketHandler(WebSocketHandler):
    async def on_message(self, message: SubscribeEvent):
        await super().on_message(message)
        
        # Store chat group ID from metadata if we don't have one yet
        if message.type == "chat_metadata" and not st.session_state.game.chat_group_id:
            st.session_state.game.chat_group_id = message.chat_group_id
            print(f"Chat group ID set: {message.chat_group_id}")
        
        if message.type in ["user_message", "assistant_message"]:
            role = message.message.role
            message_text = message.message.content
            
            # Create emotion text if available
            emotion_text = ""
            if message.from_text is False and hasattr(message, 'models') and hasattr(message.models, 'prosody'):
                scores = dict(message.models.prosody.scores)
                top_3_emotions = self._extract_top_n_emotions(scores, 3)
                emotion_text = " | ".join([f"{emotion} ({score:.2f})" for emotion, score in top_3_emotions.items()])
            
            # Add message to session state
            content = f"{message_text}\n\n*Emotions: {emotion_text}*" if emotion_text else message_text
            with st.chat_message(role):
                st.markdown(content)
            print("st.session_state.messages", st.session_state.messages)
            
            # Force streamlit to rerun and update the UI
            # st.rerun()

async def create_hume_config(system_prompt: str) -> str:
    """Create a new Hume.ai config with custom system prompt"""
    url = "https://api.hume.ai/v0/evi/configs"
    headers = {
        "X-Hume-Api-Key": os.getenv("HUME_API_KEY"),
        "Content-Type": "application/json"
    }
    
    data = {
        "evi_version": "2",
        "name": f"Prisoner's Dilemma Config {int(time.time())}",
        "language_model": {
            "model_provider": "ANTHROPIC",
            "model_resource": "claude-3-5-sonnet-20240620",
            "temperature": 1
        },
        "event_messages": {
            "on_new_chat": {
            "enabled": True,
            "text": ""
            },
        },
        "prompt": {
            "text": system_prompt
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if 200 <= response.status_code < 300:
            return response.json()["id"]
        else:
            st.error(f"{response.status_code}  Failed to create config: {response.text}")
            return os.getenv("HUME_CONFIG_ID")  # Fallback to default config

async def run_chat():
    # Initialize client and handlers
    client = AsyncHumeClient(api_key=os.getenv("HUME_API_KEY"))
    
    # Check if system prompt was modified
    config_id = os.getenv("HUME_CONFIG_ID")
    if st.session_state.system_prompt != DEFAULT_PROMPT:
        config_id = await create_hume_config(st.session_state.system_prompt)
    
    # Add resumed_chat_group_id to options if we have one
    options_dict = {
        "config_id": config_id,
        "secret_key": os.getenv("HUME_SECRET_KEY")
    }
    
    # If we have a chat group ID, use it to resume the conversation
    if st.session_state.game.chat_group_id:
        options_dict["resumed_chat_group_id"] = st.session_state.game.chat_group_id
    
    options = ChatConnectOptions(**options_dict)
    websocket_handler = StreamlitWebSocketHandler()
    async with client.empathic_voice.chat.connect_with_callbacks(
        options=options,
        on_open=websocket_handler.on_open,
        on_message=websocket_handler.on_message,
        on_close=websocket_handler.on_close,
        on_error=websocket_handler.on_error
    ) as socket:
        websocket_handler.set_socket(socket)
        
        # Create microphone interface task
        microphone_task = asyncio.create_task(
            MicrophoneInterface.start(
                socket,
                allow_user_interrupt=False,
                byte_stream=websocket_handler.byte_strs
            )
        )
        
        await microphone_task

async def handle_conversation_phase():
    """Handle the CONVERSATION phase with timer and chat"""
    timer_placeholder = st.empty()
    
    async def on_timer_complete():
        st.session_state.game.phase = "USER_DECISION"
        st.session_state.game.timer_start = None
        st.rerun()
    
    timer = AsyncTimer(30, on_timer_complete, timer_placeholder)
    await asyncio.gather(
        timer.start(),
        run_chat()
    )

# Display welcome message
if len(st.session_state.messages) == 0:
    st.info("Welcome to the Hume.ai Voice Chat Demo! Click the button below to start chatting.")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat controls
col1, col2 = st.columns(2)

with col1:
    if st.button("Start Recording" if not st.session_state.recording else "Stop Recording"):
        st.session_state.recording = not st.session_state.recording
        if st.session_state.recording:
            asyncio.run(run_chat())

with col2:
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.recording = False
        st.rerun()

# Initialize session state
if 'game' not in st.session_state:
    st.session_state.game = GameState()

# Game UI based on phase
if st.session_state.game.phase == "INIT":
    st.markdown("### Configure AI Behavior")
    
    # System prompt configuration
    st.text_area(
        "System Prompt",
        value=st.session_state.system_prompt,
        height=200,
        key="system_prompt",
        help="Configure how the AI should behave during the conversation"
    )
    
    if st.button("Start Game"):
        st.session_state.game.phase = "CONVERSATION"
        st.session_state.game.timer_start = time.time()
        st.rerun()

elif st.session_state.game.phase == "CONVERSATION":
    asyncio.run(handle_conversation_phase())

elif st.session_state.game.phase == "USER_DECISION":
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cooperate"):
            st.session_state.game.user_decisions.append("C")
            st.session_state.game.phase = "AI_DECISION"
            st.rerun()
    with col2:
        if st.button("Defect"):
            st.session_state.game.user_decisions.append("D")
            st.session_state.game.phase = "AI_DECISION"
            st.rerun()

elif st.session_state.game.phase == "AI_DECISION":
    # Run AI decision chat
    asyncio.run(run_chat())

elif st.session_state.game.phase == "RESULTS":
    # Display round results
    # Update scores
    if st.button("Next Round"):
        st.session_state.game.round += 1
        st.session_state.game.phase = "CONVERSATION"
        st.session_state.game.timer_start = time.time()
        st.rerun()

def check_timer():
    if st.session_state.game.timer_start:
        elapsed = time.time() - st.session_state.game.timer_start
        if elapsed >= 30:
            st.session_state.game.phase = "USER_DECISION"
            st.session_state.game.timer_start = None
            st.rerun()
