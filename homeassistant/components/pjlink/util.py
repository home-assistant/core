"""Common PJLink utilities and types."""

from typing import Any, NamedTuple, TypedDict

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT

from .const import CONF_ENCODING, DEFAULT_TIMEOUT


def format_input_source(input_source_name: str, input_source_number: int) -> str:
    """Format input source for display in UI."""
    return f"{input_source_name} {input_source_number}"


class LampStateType(TypedDict):
    """Lamp state typed definition."""

    state: bool
    hours: int


class PJLinkConfig(NamedTuple):
    """Configuration options for a PJLink device."""

    host: str
    port: int
    name: str
    encoding: str
    password: str
    timeout: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PJLinkConfig":
        """Create a PJLinkConfig from a dictionary."""
        return cls(
            data[CONF_HOST],
            data[CONF_PORT],
            data[CONF_NAME],
            data[CONF_ENCODING],
            data[CONF_PASSWORD],
            DEFAULT_TIMEOUT,
        )
