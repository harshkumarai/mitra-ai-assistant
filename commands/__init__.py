"""
commands/__init__.py
--------------------
Command registry and dispatcher.
`get_command_handler` is the single public function that the rest of the
application calls. It inspects the user's input text and returns the most
appropriate BaseCommand subclass instance.

Adding a new command type:
  1. Create a class in this package that extends BaseCommand.
  2. Register it in the COMMAND_REGISTRY list below.
     Commands are checked in order; the first match wins.
"""

import re
from commands.base_command import BaseCommand
from commands.system_commands import SystemCommand
from commands.web_commands import WebCommand
from commands.utility_commands import UtilityCommand
from commands.ai_command import AICommand

# Registry: (trigger_keywords_tuple, handler_class)
# Keywords are matched as whole words (word-boundary regex) so "time" won't
# accidentally match inside "times" or "sometime".
COMMAND_REGISTRY = [
    (("open", "launch", "start", "shutdown", "restart", "volume"), SystemCommand),
    (("search", "google", "youtube", "open website", "browse"), WebCommand),
    (("calculate", "what is", "how much", "weather"), UtilityCommand),
    (("time", "date"), UtilityCommand),
]

_DEFAULT_HANDLER = AICommand


def _matches(text: str, keywords: tuple) -> bool:
    """Return True if any keyword matches as a whole word in text."""
    for kw in keywords:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, text):
            return True
    return False


def get_command_handler(text: str, context=None) -> "BaseCommand":
    """
    Return the right command handler for the given input text.

    Parameters
    ----------
    text : str
        The raw transcribed user input.
    context : ConversationContext, optional
        The current short-term context (passed through for stateful commands).

    Returns
    -------
    BaseCommand
        An instantiated handler ready to be `.execute()`-d.
    """
    lowered = text.lower()
    for keywords, handler_class in COMMAND_REGISTRY:
        if _matches(lowered, keywords):
            return handler_class()
    return _DEFAULT_HANDLER()
