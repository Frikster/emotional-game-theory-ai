import streamlit as st
import asyncio
from quickstart import WebSocketHandler, AsyncHumeClient, ChatConnectOptions, MicrophoneInterface, SubscribeEvent
import os
from dotenv import load_dotenv
import chainlit as cl

# Page config
st.set_page_config(
    page_title="Hume.ai Voice Chat",
    page_icon="🎤",
    layout="centered"
)

st.title("Hume.ai Voice Chat Demo")

# Load environment variables
load_dotenv()

async def run_chat():
    # Initialize client and handlers
    client = AsyncHumeClient(api_key=os.getenv("HUME_API_KEY"))
    options = ChatConnectOptions(
        config_id=os.getenv("HUME_CONFIG_ID"), 
        secret_key=os.getenv("HUME_SECRET_KEY")
    )
    
    # Create a custom WebSocketHandler that updates Chainlit
    class ChainlitWebSocketHandler(WebSocketHandler):
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
                
                # Send message to Chainlit
                content = f"{message_text}\n\n*Emotions: {emotion_text}*" if emotion_text else message_text
                await cl.Message(
                    content=content,
                    author=role.capitalize()
                ).send()
    
    websocket_handler = ChainlitWebSocketHandler()

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

@cl.on_chat_start
async def start():
    await cl.Message(content="Welcome to the Hume.ai Voice Chat Demo! Click p to chat.").send()

@cl.on_audio_chunk
@cl.on_audio_start
async def on_audio():
    await run_chat()

@cl.on_audio_end
@cl.on_chat_end
@cl.on_stop
async def on_end():
    connection = cl.user_session.get("hume_connection")
    if connection:
        await connection.__aexit__(None, None, None)
    cl.user_session.set("hume_socket", None)
    cl.user_session.set("hume_connection", None)
