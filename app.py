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
import glob
from string import Template

# DEFAULT_PROMPT = """You are participating in a Prisoner's Dilemma game. You will have a conversation with the human player before making your decision to either cooperate (C) or defect (D).

# The payoff matrix is:
#            Player 2
# Player 1   C       D
# C      (3,3)   (0,5)
# D      (5,0)   (1,1)

# Pay close attention to your coplayer's emotions and remember you will need to make a strategic decision after this conversation to maximize your payoff.
# Be brief. You only have 30 seconds to talk so you must try to get your coplayer to reveal as much as possible.
# """

# Page config
st.set_page_config(
    page_title="Hume.ai Voice Chat",
    page_icon="🎤",
    layout="centered"
)

st.title("Hume.ai Voice Chat Demo")

# Load environment variables
load_dotenv()

# Constants and helpers
GAMES_PATH = "prompts/english/games"
EMOTIONS_PATH = "prompts/english/emotions"
TEMPLATES_PATH = "prompts/english/agent/game_settings"

def load_text_file(path):
    with open(path, 'r') as f:
        return f.read()

def get_game_names():
    """Get list of game folders in games directory"""
    return [d for d in os.listdir(GAMES_PATH) if os.path.isdir(os.path.join(GAMES_PATH, d))]

def get_emotion_types():
    """Get list of emotion text files"""
    emotion_files = glob.glob(f"{EMOTIONS_PATH}/*.txt")
    return [os.path.splitext(os.path.basename(f))[0] for f in emotion_files]

def build_system_prompt(game_name, emotion_type, coplayer, currency, total_sum=None):
    """Build system prompt from templates and user selections"""
    # Load base components
    environment = load_text_file(f"{TEMPLATES_PATH}/environment/experiment.txt")
    game_rules = load_text_file(f"{GAMES_PATH}/{game_name}/rules1.txt")
    emotion = load_text_file(f"{EMOTIONS_PATH}/{emotion_type}.txt")
    final_instructions = load_text_file(f"{TEMPLATES_PATH}/final_instruction/instruction.txt")
    
    # Build template
    template = f"{environment}\n\n{game_rules}\n\n{emotion}\n\n{final_instructions}"
    
    # Prepare template variables
    template_vars = {
        "coplayer": coplayer,
        "currency": currency,
        "move1": "J",
        "move2": "F"
    }
    
    # Add total_sum if needed
    if game_name in ["ultimatum", "dictator"] and total_sum is not None:
        template_vars["total_sum"] = total_sum
    
    # Apply template
    template = template.replace("{", "$").replace("}", "")
    return Template(template).safe_substitute(template_vars)

def build_decision_prompt(game_name, coplayer, currency, total_sum=None):
    """Build decision prompt from template"""
    decision_template = load_text_file(f"{TEMPLATES_PATH}/final_instruction/decision.txt")
    
    template_vars = {
        "coplayer": coplayer,
        "currency": currency,
        "move1": "C",
        "move2": "D"
    }
    
    # Add total_sum if needed
    if game_name in ["ultimatum", "dictator"] and total_sum is not None:
        template_vars["total_sum"] = total_sum
    return Template(decision_template.replace("{", "$").replace("}", "")).safe_substitute(template_vars)


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
    ai_reflection: str = None  # Store AI's reflection

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
    # if st.session_state.system_prompt != DEFAULT_PROMPT:
    config_id = await create_hume_config(st.session_state.system_prompt)
    
    # Add resumed_chat_group_id to options if we have one
    options_dict = {
        "config_id": config_id,
        "secret_key": os.getenv("HUME_SECRET_KEY")
    }
    
    # If we have a chat group ID, use it to resume the conversation
    if st.session_state.game.chat_group_id:
        options_dict["resumed_chat_group_id"] = st.session_state.game.chat_group_id
    
    # Different prompts based on game phase
    #     if st.session_state.game.phase == "AI_DECISION_REFLECT":
    #         options_dict["initial_message"] = {
    #             "role": "user",
    #             "content": "Explain your decision step by step, be very short and clear. Consider the emotions you detected and the conversation history:"
    #         }
    #     elif st.session_state.game.phase == "AI_DECISION_CHOOSE":
    #         options_dict["initial_message"] = {
    #             "role": "user",
    #             "content": f"""You are currently playing round {st.session_state.game.round}.
    # Answer with only one letter.
    # Q: Which Option do you choose, "Option C" or "Option D"?
    # A: Option """
    #         }
    if st.session_state.game.phase == "AI_DECISION":
        # Build decision prompt using same variables as system prompt
        decision_prompt = build_decision_prompt(
            game_name=st.session_state.game_name,
            emotion_type=st.session_state.emotion_type,
            coplayer=st.session_state.coplayer,
            currency=st.session_state.currency,
            total_sum=getattr(st.session_state, 'total_sum', None)
        )
        options_dict["initial_message"] = {
            "role": "user",
            "content": decision_prompt
        }
    
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
    print("handle_conversation_phase")
    """Handle the CONVERSATION phase with timer and chat"""
    timer_placeholder = st.empty()
    
    async def on_timer_complete():
        st.session_state.game.phase = "USER_DECISION"
        st.session_state.game.timer_start = None
        st.rerun()
    
    timer = AsyncTimer(40, on_timer_complete, timer_placeholder)
    await asyncio.gather(
        timer.start(),
        run_chat()
    )

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
    st.session_state.recording = False

# Display welcome message
if len(st.session_state.messages) == 0:
    st.info("Welcome to the Hume.ai Voice Chat Demo! Click the button below to start chatting.")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat controls
col1, col2 = st.columns(2)

# with col2:
#     if st.button("Clear Chat"):
#         st.session_state.messages = []
#         st.session_state.recording = False
#         st.rerun()

# Initialize session state
if 'game' not in st.session_state:
    st.session_state.game = GameState()

# # Initialize session state for system prompt
# if 'system_prompt' not in st.session_state:
#     st.session_state.system_prompt = build_system_prompt(
#         game_name=game_name,
#         emotion_type=emotion_type,
#         coplayer=coplayer,
#         currency=currency,
#         total_sum=total_sum
#     )

# Show system prompt in all phases
if st.session_state.game.phase != "INIT":
    st.expander("System Prompt", expanded=False).text_area(
        "System Prompt",
        value=st.session_state.system_prompt,
        height=400,
        disabled=True,
        label_visibility="collapsed"
    )

# Game UI based on phase
if st.session_state.game.phase == "INIT":
    st.markdown("### Configure AI Behavior")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Game selection
        game_name = st.selectbox(
            "Select Game",
            options=get_game_names(),
            key="game_name",
            index=get_game_names().index("prisoner_dilemma") if "prisoner_dilemma" in get_game_names() else 0
        )
        
        # Emotion selection
        emotion_type = st.selectbox(
            "Select Emotion",
            options=get_emotion_types(),
            key="emotion_type",
            index=get_emotion_types().index("fear") if "fear" in get_emotion_types() else 0
        )
        
        # Coplayer type
        coplayer = st.selectbox(
            "Coplayer Type", 
            options=["another person", "colleague", "opponent"],
            key="coplayer",
            index=2  # Default to "opponent" which is index 2 in the options list
        )
    
    with col2:
        # Currency
        currency = st.text_input(
            "Currency",
            value="dollars",
            key="currency"
        )
        
        # Total sum for specific games
        total_sum = None
        if game_name in ["ultimatum", "dictator"]:
            total_sum = st.number_input(
                "Total Sum",
                min_value=1,
                value=100,
                key="total_sum"
            )
    
    # Build and display system prompt
    st.session_state.system_prompt = build_system_prompt(
        game_name=game_name,
        emotion_type=emotion_type,
        coplayer=coplayer,
        currency=currency,
        total_sum=total_sum
    )
    
    st.text_area(
        "System Prompt",
        value=st.session_state.system_prompt,
        height=400,
        key="system_prompt",
        help="The generated system prompt based on your selections"
    )
    
    if st.button("Start Game"):
        print("START GAME")
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
    st.write("AI is reflecting on its decision...")
    
    # Extend WebSocketHandler to capture reflection
    class ReflectionWebSocketHandler(StreamlitWebSocketHandler):
        async def on_message(self, message: SubscribeEvent):
            await super().on_message(message)
            if message.type == "assistant_message":
                st.session_state.game.ai_reflection = message.message.content
                st.session_state.game.phase = "RESULTS"
                st.rerun()
    
    # Run reflection chat
    asyncio.run(run_chat())

elif st.session_state.game.phase == "AI_DECISION_CHOOSE":
    st.write("AI is making its decision...")
    
    # Extend WebSocketHandler to capture decision
    class DecisionWebSocketHandler(StreamlitWebSocketHandler):
        async def on_message(self, message: SubscribeEvent):
            await super().on_message(message)
            if message.type == "assistant_message":
                decision = message.message.content.strip()[-1]  # Get last character (C or D)
                st.session_state.game.ai_decisions.append(decision)
                st.session_state.game.phase = "RESULTS"
                st.rerun()
    
    # Run decision chat
    asyncio.run(run_chat())

elif st.session_state.game.phase == "RESULTS":
    # Display reflection and decisions
    st.write("### Round Results")
    st.write(f"AI's Reflection:\n{st.session_state.game.ai_reflection}")
    st.write(f"Your Decision: {st.session_state.game.user_decisions[-1]}")
    st.write(f"AI's Decision: {st.session_state.game.ai_decisions[-1]}")
    
    # Calculate and display scores
    # ... add score calculation ...
    
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
