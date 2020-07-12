"""Helpers for logging allowing more advanced logging styles to be used."""
import inspect
import logging
from typing import Any, Mapping, MutableMapping, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.loader import bind_hass

LOGGER_LEVELS = "logger_levels"

LOGSEVERITY = {
    "CRITICAL": 50,
    "FATAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "WARN": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}


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
        self, logger: logging.Logger, extra: Optional[Mapping[str, Any]] = None
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
    ) -> Tuple[Any, MutableMapping[str, Any]]:
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


@bind_hass
def set_default_log_level(hass: HomeAssistant, namespace: str, loglevel: int) -> None:
    """Set the log level as long as logger has not overridden it."""
    if LOGGER_LEVELS not in hass.data or namespace in hass.data[LOGGER_LEVELS]:
        return

    logging.getLogger(namespace).setLevel(loglevel)


@bind_hass
def restore_log_level(hass: HomeAssistant, namespace: str) -> None:
    """Restore the log level to the level configured by the logger integration."""
    if LOGGER_LEVELS not in hass.data or namespace not in hass.data[LOGGER_LEVELS]:
        return

    logging.getLogger(namespace).setLevel(
        LOGSEVERITY[hass.data[LOGGER_LEVELS][namespace]]
    )
