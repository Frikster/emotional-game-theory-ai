import asyncio
import time
import streamlit as st
from typing import Callable, Optional

class AsyncTimer:
    def __init__(self, duration: int, on_complete: Callable, placeholder: Optional[st.empty] = None):
        """
        Initialize async timer
        
        Args:
            duration: Duration in seconds
            on_complete: Callback function to run when timer completes
            placeholder: Optional streamlit placeholder to display timer
        """
        self.duration = duration
        self.on_complete = on_complete
        self.placeholder = placeholder or st.empty()
        self.start_time = None
        self.is_running = False

    def format_time(self, seconds: int) -> str:
        """Format seconds into MM:SS"""
        mm, ss = seconds//60, seconds%60
        return f"{mm:02d}:{ss:02d}"

    async def start(self):
        """Start the countdown timer"""
        self.start_time = time.time()
        self.is_running = True
        
        while self.is_running:
            elapsed = int(time.time() - self.start_time)
            remaining = max(0, self.duration - elapsed)
            
            # Update display
            self.placeholder.metric(
                "Time Remaining", 
                self.format_time(remaining)
            )
            
            # Check if timer completed
            if remaining <= 0:
                self.is_running = False
                await self.on_complete()
                break
                
            await asyncio.sleep(0.1)  # Small delay to prevent excessive updates

    def stop(self):
        """Stop the timer"""
        self.is_running = False
