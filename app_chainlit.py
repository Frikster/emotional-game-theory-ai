import streamlit as st
import asyncio
from quickstart import WebSocketHandler, AsyncHumeClient, ChatConnectOptions, MicrophoneInterface, SubscribeEvent
import os
from dotenv import load_dotenv
import chainlit as cl
# from uuid import uuid4
from chainlit.logger import logger

# Page config
st.set_page_config(
    page_title="Hume.ai Voice Chat",
    page_icon="🎤",
    layout="centered"
)

st.title("Hume.ai Voice Chat Demo")

# Load environment variables
load_dotenv()

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


async def setup_hume_realtime():
    """Instantiate and configure the Hume Realtime Client"""
    client = AsyncHumeClient(api_key=os.getenv("HUME_API_KEY"))
    options = ChatConnectOptions(
        config_id=os.getenv("HUME_CONFIG_ID"), 
        secret_key=os.getenv("HUME_SECRET_KEY")
    )
    
    websocket_handler = ChainlitWebSocketHandler()
    # cl.user_session.set("track_id", str(uuid4()))

    # async def handle_conversation_updated(message):
    #     """Currently used to stream responses back to the client."""
    #     if message.type == "audio_output":
    #         # Handle audio streaming
    #         message_bytes = base64.b64decode(message.data.encode("utf-8"))
    #         await cl.context.emitter.send_audio_chunk(
    #             cl.OutputAudioChunk(
    #                 mimeType="pcm16", 
    #                 data=message_bytes, 
    #                 track=cl.user_session.get("track_id")
    #             )
    #         )
    #     elif message.type in ["user_message", "assistant_message"]:
    #         # Handle text and emotion data
    #         role = message.message.role
    #         message_text = message.message.content
            
    #         # Create emotion text if available
    #         emotion_text = ""
    #         if message.from_text is False and hasattr(message, 'models') and hasattr(message.models, 'prosody'):
    #             scores = dict(message.models.prosody.scores)
    #             top_3_emotions = websocket_handler._extract_top_n_emotions(scores, 3)
    #             emotion_text = " | ".join([f"{emotion} ({score:.2f})" for emotion, score in top_3_emotions.items()])
            
    #         # Send message to Chainlit
    #         content = f"{message_text}\n\n*Emotions: {emotion_text}*" if emotion_text else message_text
    #         await cl.Message(
    #             content=content,
    #             author=role.capitalize()
    #         ).send()

    # async def handle_conversation_interrupt(event):
    #     """Used to cancel the client previous audio playback."""
    #     cl.user_session.set("track_id", str(uuid4()))
    #     await cl.context.emitter.send_audio_interrupt()
        
    # async def handle_error(error):
    #     logger.error(error)
    #     await cl.Message(content=f"Error: {str(error)}").send()

    # Override the websocket handler's methods
    # websocket_handler.on_message = handle_conversation_updated
    # websocket_handler.on_error = handle_error
    
    # Store the handler in the session
    cl.user_session.set("hume_websocket_handler", websocket_handler)
    cl.user_session.set("hume_client", client)
    cl.user_session.set("hume_options", options)


@cl.on_chat_start
async def start():
    await cl.Message(
        content="Welcome to the Chainlit x Hume.ai realtime example. Press `P` to talk!"
    ).send()
    await setup_hume_realtime()

# @cl.on_message
# async def on_message(message: cl.Message):
#     socket = cl.user_session.get("hume_socket")    
#     if socket and socket.is_connected():
#         await socket.send_user_input(message.content)
#     else:
#         await cl.Message(content="Please activate voice mode before sending messages!").send()

@cl.on_audio_start
async def on_audio_start():
    try:
        client = cl.user_session.get("hume_client")
        options = cl.user_session.get("hume_options")
        websocket_handler = cl.user_session.get("hume_websocket_handler")
        
        if not all([client, options, websocket_handler]):
            raise Exception("Hume.ai client not properly initialized!")
        
        # Create a new context manager    
        connection = client.empathic_voice.chat.connect_with_callbacks(
            options=options,
            on_open=websocket_handler.on_open,
            on_message=websocket_handler.on_message,
            on_close=websocket_handler.on_close,
            on_error=websocket_handler.on_error
        )
        
        # Enter the context manager
        socket = await connection.__aenter__()
        
        websocket_handler.set_socket(socket)
        cl.user_session.set("hume_socket", socket)
        # Store the connection context manager to close it properly later
        cl.user_session.set("hume_connection", connection)
        logger.info("Connected to Hume.ai realtime")
        return True
    except Exception as e:
        await cl.ErrorMessage(content=f"Failed to connect to Hume.ai realtime: {e}").send()
        return False

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    socket = cl.user_session.get("hume_socket")
    websocket_handler = cl.user_session.get("hume_websocket_handler")
    if socket and websocket_handler:
        # # Get or create byte stream
        # if not hasattr(websocket_handler, "byte_stream"):
        #     websocket_handler.byte_stream = websocket_handler.byte_strs
        
        # Start microphone interface if not already started
        if not hasattr(websocket_handler, "microphone_task"):
            websocket_handler.microphone_task = asyncio.create_task(
                MicrophoneInterface.start(
                    socket,
                    allow_user_interrupt=False,
                    byte_stream=websocket_handler.byte_strs,
                )
            )
            await websocket_handler.microphone_task
        
        # Send audio chunk to the byte stream
        # await websocket_handler.byte_stream.put(chunk.data)
    else:
        logger.info("Hume.ai socket is not connected")

@cl.on_audio_end
@cl.on_chat_end
@cl.on_stop
async def on_end():
    connection = cl.user_session.get("hume_connection")
    if connection:
        await connection.__aexit__(None, None, None)
    cl.user_session.set("hume_socket", None)
    cl.user_session.set("hume_connection", None)
