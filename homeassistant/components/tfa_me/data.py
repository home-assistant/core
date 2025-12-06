"""TFA.me station integration: data.py."""

from dataclasses import dataclass

from .coordinator import TFAmeDataCoordinator


@dataclass
class TFAmeData:
    """Store TFA.me runtime data."""

    def __init__(self, host: str) -> None:
        """Initialize client with host."""

        if host == "":
            raise TFAmeException("host_empty")

        self.host = host
        self.coordinator: TFAmeDataCoordinator

    async def get_identifier(self) -> str:
        """Request a unique ID from a device, we just take the host name."""
        return self.host


class TFAmeException(Exception):
    """User defined exception for error in client."""
