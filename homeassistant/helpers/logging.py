"""Helpers for logging allowing more advanced logging styles to be used."""
import inspect
import logging


class BraceMessage:
    """
    Represents a logging message with brace style arguments.

    Adapted from: https://stackoverflow.com/a/24683360/2267718
    """

    def __init__(self, fmt, args, kwargs):
        """Initialize a new BraceMessage object."""
        self._fmt = fmt
        self._args = args
        self._kwargs = kwargs

    def __str__(self):
        """Convert the object to a string for logging."""
        return str(self._fmt).format(*self._args, **self._kwargs)


class BraceStyleAdapter(logging.LoggerAdapter):
    """Represents an adapter wrapping the logger allowing BraceMessages."""

    def __init__(self, logger, extra=None):
        """Initialize a new StyleAdapter for the provided logger."""
        super(BraceStyleAdapter, self).__init__(logger, extra or {})

    def log(self, level, msg, *args, **kwargs):
        """Log the message provided at the appropriate level."""
        if self.isEnabledFor(level):
            msg, log_kwargs = self.process(msg, kwargs)
            self.logger._log(  # pylint: disable=protected-access
                level, BraceMessage(msg, args, kwargs), (), **log_kwargs
            )

    def process(self, msg, kwargs):
        """Process the keyward args in preparation for logging."""
        return (
            msg,
            {
                k: kwargs[k]
                for k in inspect.getfullargspec(
                    self.logger._log  # pylint: disable=protected-access
                ).args[1:] if k in kwargs
            }
        )