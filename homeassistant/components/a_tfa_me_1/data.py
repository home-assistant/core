"""TFA.me station integration: data.py."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

type TFAmeConfigEntry = ConfigEntry[TFAmeData]


@dataclass
class TFAmeData:
    """Store runtime data."""

    def __init__(self, host: str) -> None:
        """Initialize client with host."""

        # if host== "unfug":
        #    raise TFAmeException("Host empty")

        self.host = host

    async def get_identifier(self) -> str:
        """Request a unique ID from a device."""
        # We just take the host name
        return self.host


class TFAmeException(Exception):
    """User defined exception for error in client."""
