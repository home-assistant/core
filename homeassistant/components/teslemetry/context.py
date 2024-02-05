"""Teslemetry context managers."""

from contextlib import contextmanager

from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.exceptions import HomeAssistantError


@contextmanager
def handle_command():
    """Handle wake up and errors."""
    try:
        yield
    except TeslaFleetError as e:
        raise HomeAssistantError("Teslemetry command failed") from e
