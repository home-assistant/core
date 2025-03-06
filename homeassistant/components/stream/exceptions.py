"""Stream component exceptions."""

from homeassistant.exceptions import HomeAssistantError

from .const import StreamClientError


class StreamOpenClientError(HomeAssistantError):
    """Raised when client error received when trying to open a stream.

    :param stream_client_error: The type of client error
    """

    def __init__(self, message: str, error_code: StreamClientError) -> None:
        """Initialize a stream open client error."""
        super().__init__(message)
        self.error_code = error_code


class StreamWorkerError(Exception):
    """An exception thrown while processing a stream."""

    def __init__(
        self, message: str, error_code: StreamClientError = StreamClientError.Other
    ) -> None:
        """Initialize a stream worker error."""
        super().__init__(message)
        self.error_code = error_code


class StreamEndedError(StreamWorkerError):
    """Raised when the stream is complete, exposed for facilitating testing."""
