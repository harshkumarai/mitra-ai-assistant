"""
commands/web_commands.py
------------------------
Handles web-related commands:
  - Google search   ("search for Python tutorials")
  - YouTube search  ("play lofi music on YouTube")
  - Open a website  ("open github.com")

Opens URLs in the system default browser using `webbrowser.open()` so the
module stays dependency-free and cross-platform.
"""

import webbrowser
from urllib.parse import quote_plus
from commands.base_command import BaseCommand
from utilities.logger import get_logger

logger = get_logger(__name__)

# URL templates
_GOOGLE_URL = "https://www.google.com/search?q={query}"
_YOUTUBE_URL = "https://www.youtube.com/results?search_query={query}"


class WebCommand(BaseCommand):
    """Opens browser windows / tabs in response to web-related requests."""

    def execute(self, text: str, context) -> str:
        lowered = text.lower()

        if "youtube" in lowered:
            query = self._extract_query(lowered, ("youtube", "play", "search"))
            return self._open_youtube(query)

        if any(kw in lowered for kw in ("open website", "open site", "browse to", "go to")):
            url = self._extract_url(lowered)
            return self._open_url(url)

        # Default: Google search
        query = self._extract_query(lowered, ("search", "google", "look up", "find"))
        return self._open_google(query)

    # ------------------------------------------------------------------
    # Action helpers
    # ------------------------------------------------------------------

    def _open_google(self, query: str) -> str:
        if not query:
            return "What would you like me to search for?"
        url = _GOOGLE_URL.format(query=quote_plus(query))
        webbrowser.open(url)
        logger.info("Google search: %s", query)
        return f"Searching Google for {query}."

    def _open_youtube(self, query: str) -> str:
        if not query:
            return "What would you like to watch on YouTube?"
        url = _YOUTUBE_URL.format(query=quote_plus(query))
        webbrowser.open(url)
        logger.info("YouTube search: %s", query)
        return f"Opening YouTube results for {query}."

    def _open_url(self, url: str) -> str:
        if not url:
            return "Please tell me the website address."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        logger.info("Opening URL: %s", url)
        return f"Opening {url} in your browser."

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_query(text: str, trigger_words: tuple) -> str:
        """Strip trigger words and return the remaining search query."""
        for kw in trigger_words:
            if kw in text:
                return text.split(kw, 1)[-1].strip()
        return text.strip()

    @staticmethod
    def _extract_url(text: str) -> str:
        """
        Pull out a domain/URL from the text.
        E.g. "open website github.com" → "github.com"
        """
        for kw in ("open website", "open site", "browse to", "go to"):
            if kw in text:
                return text.split(kw, 1)[-1].strip()
        return ""
