"""
commands/ai_command.py
----------------------
AI-powered command handler using Google Gemini for general queries.
This is the fallback handler when no specific command matches.
"""

import asyncio
import traceback
from commands.base_command import BaseCommand
from utilities.logger import get_logger
import config

logger = get_logger(__name__)

try:
    from google import genai
    _gemini_available = True
except ImportError:
    genai = None
    _gemini_available = False
    logger.warning("google-genai package not installed - AI features will be disabled.")


class AICommand(BaseCommand):
    """Handles general queries using Google Gemini AI."""

    def __init__(self):
        self._client = None
        self._model = config.GEMINI_MODEL

    def execute(self, text: str, context) -> str:
        """Execute the AI command by sending the query to Gemini."""
        if not _gemini_available:
            return (
                "AI features are not available. "
                "Please install the google-generativeai package: pip install google-generativeai"
            )

        if not config.GEMINI_API_KEY:
            return (
                "Gemini API key is not configured. "
                "Please add GEMINI_API_KEY to your jarvis/.env file."
            )

        try:
            # Run the async Gemini call in a new event loop
            response = asyncio.run(self._get_gemini_response(text, context))
            return response
        except Exception as exc:
            logger.error("AI command error: %s", traceback.format_exc())
            return f"Sorry, I encountered an error processing your request: {str(exc)}"

    async def _get_gemini_response(self, text: str, context) -> str:
        """Get response from Gemini API using the newer google-genai package."""
        try:
            # Initialize client if not already done
            if self._client is None:
                logger.info("[AI] Initializing Gemini client...")
                self._client = genai.Client(api_key=config.GEMINI_API_KEY)
                logger.info("[AI] Gemini client initialized successfully")

            # Build conversation context if available
            prompt = self._build_prompt(text, context)

            logger.info("[AI] Sending request to Gemini...")
            logger.debug("[AI] Prompt: %s", prompt[:200] + "..." if len(prompt) > 200 else prompt)

            # Generate response using the newer API
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt
            )
            
            if response and response.text:
                logger.info("[AI] Received response from Gemini (length: %d)", len(response.text))
                return response.text.strip()
            else:
                logger.warning("[AI] Empty response from Gemini")
                return "I received an empty response from the AI service."

        except Exception as exc:
            logger.error("[AI] Gemini API error: %s", traceback.format_exc())
            # Provide user-friendly error messages
            error_msg = str(exc).lower()
            if "api key" in error_msg or "authentication" in error_msg or "401" in error_msg or "403" in error_msg:
                return "Invalid Gemini API key. Please check your GEMINI_API_KEY in jarvis/.env file."
            elif "quota" in error_msg or "rate limit" in error_msg or "429" in error_msg:
                return "Gemini rate limit reached. Please wait a moment before retrying."
            elif "503" in error_msg or "unavailable" in error_msg or "high demand" in error_msg:
                return "Gemini is currently experiencing high demand. Please try again in a few moments."
            else:
                return f"Sorry, I couldn't get a response from Gemini: {str(exc)}"

    def _build_prompt(self, text: str, context) -> str:
        """Build the prompt with conversation context."""
        prompt = f"User: {text}\n\nPlease provide a helpful, concise response."

        # Add conversation context if available
        if context and hasattr(context, 'history'):
            recent_history = context.history[-3:] if len(context.history) > 3 else context.history
            if recent_history:
                prompt = "Previous conversation:\n"
                for turn in recent_history:
                    role = turn.get('role', 'user')
                    content = turn.get('content', '')
                    prompt += f"{role.capitalize()}: {content}\n"
                prompt += f"\nCurrent user message: {text}\n\nPlease provide a helpful, concise response."

        return prompt
