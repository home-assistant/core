"""Wraps the home assistance logger for Contec nuget use."""
from logging import Logger

from ContecControllers.ITracer import ITracer


class ContecTracer(ITracer):
    """Wraps the home assistance logger for Contec nuget use."""

    _logger: Logger

    def __init__(self, logger: Logger) -> None:
        """Init the ContecTracer class."""
        super().__init__()
        self._logger = logger

    def TraceVerbose(self, message: str) -> None:
        """Trace verbose message."""
        self._logger.debug(message)

    def TraceInformation(self, message: str) -> None:
        """Trace information message."""
        self._logger.info(message)

    def TraceWarning(self, message: str) -> None:
        """Trace warning message."""
        self._logger.warn(message)

    def TraceError(self, message: str) -> None:
        """Trace error message."""
        self._logger.error(message)
