import streamlit as st
import asyncio
from quickstart import WebSocketHandler, AsyncHumeClient, ChatConnectOptions, MicrophoneInterface
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

async def run_chat():
    # Initialize client and handlers
    client = AsyncHumeClient(api_key=st.secrets["HUME_API_KEY"])
    options = ChatConnectOptions(
        config_id=st.secrets["HUME_CONFIG_ID"], 
        secret_key=st.secrets["HUME_SECRET_KEY"]
    )
    
    websocket_handler = WebSocketHandler()

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

if st.button("Start Chat"):
    asyncio.run(run_chat()) 