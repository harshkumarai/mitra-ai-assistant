"""
commands/base_command.py
------------------------
Abstract base class for every command handler.

All command modules must subclass BaseCommand and implement `execute`.
This enforces a uniform interface so the dispatcher in __init__.py can
call any handler the same way, regardless of what it does internally.
"""

from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """
    Contract that every command handler must fulfil.

    Methods
    -------
    execute(text, context) -> str
        Process the user's transcribed text and return the spoken response.
    can_handle(text) -> bool   [optional override]
        Return True if this handler is confident it can process `text`.
        The default implementation always returns True so that a handler
        registered as a fallback still works.
    """

    @abstractmethod
    def execute(self, text: str, context) -> str:
        """
        Execute the command and return the assistant's spoken reply.

        Parameters
        ----------
        text : str
            The raw transcribed user input (already lower-cased by caller).
        context : ConversationContext
            Short-term conversation context for stateful interactions.

        Returns
        -------
        str
            The text the assistant will speak aloud.
        """

    def can_handle(self, text: str) -> bool:
        """Return True if this handler believes it can process the input."""
        return True
