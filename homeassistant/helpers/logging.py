"""Helpers for logging allowing more advanced logging styles to be used."""
from __future__ import annotations

from collections.abc import Mapping, MutableMapping
import inspect
import logging
from typing import Any


class KeywordMessage:
    """
    Represents a logging message with keyword arguments.

    Adapted from: https://stackoverflow.com/a/24683360/2267718
    """

    def __init__(self, fmt: Any, args: Any, kwargs: Mapping[str, Any]) -> None:
        """Initialize a new KeywordMessage object."""
        self._fmt = fmt
        self._args = args
        self._kwargs = kwargs

    def __str__(self) -> str:
        """Convert the object to a string for logging."""
        return str(self._fmt).format(*self._args, **self._kwargs)


class KeywordStyleAdapter(logging.LoggerAdapter):
    """Represents an adapter wrapping the logger allowing KeywordMessages."""

    def __init__(
        self, logger: logging.Logger, extra: Mapping[str, Any] | None = None
    ) -> None:
        """Initialize a new StyleAdapter for the provided logger."""
        super().__init__(logger, extra or {})

    def log(self, level: int, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Log the message provided at the appropriate level."""
        if self.isEnabledFor(level):
            msg, log_kwargs = self.process(msg, kwargs)
            self.logger._log(  # pylint: disable=protected-access
                level, KeywordMessage(msg, args, kwargs), (), **log_kwargs
            )

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        """Process the keyword args in preparation for logging."""
        return (
            msg,
            {
                k: kwargs[k]
                for k in inspect.getfullargspec(
                    self.logger._log  # pylint: disable=protected-access
                ).args[1:]
                if k in kwargs
            },
        )
