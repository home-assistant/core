"""Keep Telegram bot tokens out of the logs.

The Telegram API embeds the bot token in the URL path, so the library, the HTTP
stack underneath it and any traceback quoting that URL all carry the token. None
of that passes through this integration's own log calls, so the only way to keep
it out of `home-assistant.log` is to scrub the records on their way out.
"""

import logging
from typing import override

REDACTED = "**REDACTED**"


class TokenRedactingFilter(logging.Filter):
    """Replace known bot tokens in log records with a placeholder."""

    def __init__(self) -> None:
        """Initialize the filter with no tokens to redact."""
        super().__init__()
        # Replaced rather than mutated, so the logging thread always reads a
        # consistent snapshot.
        self._tokens: frozenset[str] = frozenset()

    def add_token(self, token: str) -> None:
        """Start redacting a token."""
        self._tokens |= {token}

    def remove_token(self, token: str) -> None:
        """Stop redacting a token."""
        self._tokens -= {token}

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact any known token in the message and the traceback."""
        if not (tokens := self._tokens):
            return True

        message = record.getMessage()
        if any(token in message for token in tokens):
            for token in tokens:
                message = message.replace(token, REDACTED)
            record.msg = message
            record.args = None

        if record.exc_info:
            traceback = logging.Formatter().formatException(record.exc_info)
            if any(token in traceback for token in tokens):
                for token in tokens:
                    traceback = traceback.replace(token, REDACTED)
                # Hand the handler finished text so it cannot re-expand the
                # original exception.
                record.exc_text = traceback
                record.exc_info = None

        return True


_FILTER = TokenRedactingFilter()


def async_redact_token(token: str) -> None:
    """Redact a bot token from every log record from now on."""
    # The filter goes on the root handlers, not on a logger: a logger's filters
    # only see records logged through that logger, so a filter on "telegram"
    # would miss "telegram.Bot", which is where the library logs the token.
    # Handler filters see every record that reaches them.
    root = logging.getLogger()
    for handler in root.handlers:
        if _FILTER not in handler.filters:
            handler.addFilter(_FILTER)

    _FILTER.add_token(token)


def async_unredact_token(token: str) -> None:
    """Stop redacting a bot token."""
    _FILTER.remove_token(token)
