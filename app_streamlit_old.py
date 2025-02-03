import streamlit as st
import asyncio
from quickstart import WebSocketHandler, AsyncHumeClient, ChatConnectOptions, MicrophoneInterface, SubscribeEvent
import os
from dotenv import load_dotenv

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

class StreamlitWebSocketHandler(WebSocketHandler):
    async def on_message(self, message: SubscribeEvent):
        await super().on_message(message)
        
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

async def run_chat():
    # Initialize client and handlers
    client = AsyncHumeClient(api_key=os.getenv("HUME_API_KEY"))
    options = ChatConnectOptions(
        config_id=os.getenv("HUME_CONFIG_ID"), 
        secret_key=os.getenv("HUME_SECRET_KEY")
    )
    
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
