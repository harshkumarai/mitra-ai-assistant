"""
memory/context.py
-----------------
Short-term conversation context — lives only for the current session.

Stores the last N turns (user + assistant) as a list of dicts so that
command handlers can reference prior exchanges to maintain coherence.
E.g. "search that on YouTube" can look back and find "that" = "lofi music".

The window size is controlled by MAX_CONTEXT_TURNS in config.py.
"""

from collections import deque
from typing import Literal
import config


Turn = dict  # {"role": "user" | "assistant", "content": str}


class ConversationContext:
    """
    In-memory sliding window of recent conversation turns.

    Attributes
    ----------
    turns : deque[Turn]
        Fixed-size deque; oldest items are dropped automatically.
    """

    def __init__(self):
        self._turns: deque[Turn] = deque(maxlen=config.MAX_CONTEXT_TURNS)

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_turn(self, role: Literal["user", "assistant"], content: str) -> None:
        """
        Append a new turn to the context window.

        Parameters
        ----------
        role : "user" | "assistant"
        content : str
            The spoken/generated text for this turn.
        """
        self._turns.append({"role": role, "content": content})

    def clear(self) -> None:
        """Wipe the context — useful at the start of a new topic."""
        self._turns.clear()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def turns(self) -> list[Turn]:
        """Return the current context window as a plain list."""
        return list(self._turns)

    def last_user_message(self) -> str:
        """Return the most recent user turn, or empty string if none."""
        for turn in reversed(self._turns):
            if turn["role"] == "user":
                return turn["content"]
        return ""

    def to_gemini_messages(self) -> list[dict]:
        """
        Format the context window for the Gemini chat adapter.
        Returns a list of {"role": ..., "content": ...} dicts.
        """
        return [{"role": t["role"], "content": t["content"]} for t in self._turns]

    def to_messages(self) -> list[dict]:
        """Return the context window in the generic chat message format."""
        return self.to_gemini_messages()

    def __len__(self) -> int:
        return len(self._turns)

    def __repr__(self) -> str:  # handy for debugging
        return f"ConversationContext(turns={len(self._turns)}/{config.MAX_CONTEXT_TURNS})"
