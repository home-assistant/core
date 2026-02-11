"""The tests for the nexbus sensor component."""

from unittest.mock import MagicMock
from urllib.error import HTTPError

from homeassistant.components.nextbus.coordinator import NextBusHTTPError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import assert_setup_sensor
from .const import CONFIG_BASIC


async def test_setup_retry(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
) -> None:
    """Verify that a list of messages are rendered correctly."""

    mock_nextbus_predictions.side_effect = NextBusHTTPError(
        "failed", HTTPError("url", 500, "error", MagicMock(), None)
    )
    await assert_setup_sensor(
        hass, CONFIG_BASIC, expected_state=ConfigEntryState.SETUP_RETRY
    )
