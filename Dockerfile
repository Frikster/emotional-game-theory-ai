# Get a distribution that has uv already installed
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Install system dependencies for audio processing
RUN apt-get update
RUN apt-get --yes install libasound2-dev libportaudio2 ffmpeg gcc python3-dev

# Add user - this is the user that will run the app
# If you do not set user, the app will run as root (undesirable)
RUN useradd -m -u 1000 user
USER user

# Set the home directory and path
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

ENV UVICORN_WS_PROTOCOL=websockets

# Set the working directory
WORKDIR $HOME/app

# Copy the app to the container
COPY --chown=user . $HOME/app

# Install the dependencies
RUN uv sync
RUN . .venv/bin/activate && uv pip install "hume[microphone]"

# Expose the Chainlit port
EXPOSE 7860

# Run the Chainlit app
CMD ["uv", "run", "chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "7860"]