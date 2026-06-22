"""
commands/utility_commands.py
-----------------------------
General-purpose utility commands that don't fit other categories:
  - Current time / date
  - Basic arithmetic  ("what is 15 times 7")
  - Simple weather    ("what's the weather in London")
  - Catch-all fallback handling for unmatched utility input

The weather feature requires a free OpenWeatherMap API key set in .env:
    OPENWEATHERMAP_API_KEY=your_key_here
"""

import os
import re
import math
import datetime
import requests
from commands.base_command import BaseCommand
from utilities.logger import get_logger

logger = get_logger(__name__)

_OWM_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
_OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


class UtilityCommand(BaseCommand):
    """Handles time, date, math, weather, and fallback queries."""

    def execute(self, text: str, context) -> str:
        lowered = text.lower()

        # Math check FIRST — must come before time/date so "25 times 4" doesn't
        # trigger the time handler (the word "times" contains "time")
        if re.search(r"\b(calculate|how much|plus|minus|times|divided|multiplied)\b", lowered):
            return self._calculate(lowered)

        if re.search(r"\bwhat is\b", lowered) and not re.search(r"\bwhat is (the )?(time|date)\b", lowered):
            return self._calculate(lowered)

        if re.search(r"\btime\b", lowered):
            return self._tell_time()

        if re.search(r"\bdate\b", lowered):
            return self._tell_date()

        if "weather" in lowered:
            return self._get_weather(lowered)

        # Generic fallback
        return (
            "I heard you say: \"" + text + "\". "
            "I don't have a specific handler for that yet. "
            "Try asking for the time, date, a calculation, or a web search."
        )

    # ------------------------------------------------------------------
    # Time & Date
    # ------------------------------------------------------------------

    @staticmethod
    def _tell_time() -> str:
        now = datetime.datetime.now()
        return f"The current time is {now.strftime('%I:%M %p')}."

    @staticmethod
    def _tell_date() -> str:
        today = datetime.date.today()
        return f"Today is {today.strftime('%A, %B %d, %Y')}."

    # ------------------------------------------------------------------
    # Basic Arithmetic
    # ------------------------------------------------------------------

    def _calculate(self, text: str) -> str:
        """
        Attempt to evaluate a simple arithmetic expression extracted from text.
        Converts spoken words to operators before evaluation.
        """
        expr = text
        replacements = {
            "what is": "", "calculate": "", "how much is": "",
            "plus": "+", "minus": "-", "times": "*",
            "multiplied by": "*", "divided by": "/",
            "to the power of": "**", "squared": "**2",
        }
        for word, symbol in replacements.items():
            expr = expr.replace(word, symbol)

        # Keep only safe characters
        expr = re.sub(r"[^0-9+\-*/().\s\*]", "", expr).strip()

        if not expr:
            return "I couldn't understand that calculation. Please rephrase."

        try:
            result = eval(expr, {"__builtins__": {}}, {"math": math})  # noqa: S307
            return f"The answer is {result}."
        except Exception as exc:  # noqa: BLE001
            logger.warning("Calculation failed for '%s': %s", expr, exc)
            return "Sorry, I wasn't able to calculate that."

    # ------------------------------------------------------------------
    # Weather
    # ------------------------------------------------------------------

    def _get_weather(self, text: str) -> str:
        if not _OWM_API_KEY:
            return (
                "Weather lookup isn't configured. "
                "Add your OPENWEATHERMAP_API_KEY to the .env file."
            )

        city = self._extract_city(text)
        if not city:
            return "Which city's weather would you like to know?"

        try:
            resp = requests.get(
                _OWM_URL,
                params={"q": city, "appid": _OWM_API_KEY, "units": "metric"},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            return f"The weather in {city.title()} is {desc} with a temperature of {temp}°C."
        except requests.RequestException as exc:
            logger.error("Weather API error: %s", exc)
            return f"Sorry, I couldn't fetch the weather for {city}."

    @staticmethod
    def _extract_city(text: str) -> str:
        """Extract city name after 'in' or 'for' keyword."""
        for prep in (" in ", " for "):
            if prep in text:
                return text.split(prep, 1)[-1].strip()
        return ""
