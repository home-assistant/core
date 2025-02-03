"""Test time entities for the LetPot integration."""

from datetime import time
from unittest.mock import MagicMock

from letpot.exceptions import LetPotConnectionException, LetPotException
import pytest

from homeassistant.components.time import SERVICE_SET_VALUE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "user_error"),
    [
        (
            LetPotConnectionException("Connection failed"),
            "An error occurred while communicating with the LetPot device: Connection failed",
        ),
        (
            LetPotException("Random thing failed"),
            "An unknown error occurred while communicating with the LetPot device: Random thing failed",
        ),
    ],
)
async def test_time_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    exception: Exception,
    user_error: str,
) -> None:
    """Test time entity exception handling."""
    await setup_integration(hass, mock_config_entry)

    mock_device_client.set_light_schedule.side_effect = exception

    assert hass.states.get("time.garden_light_on") is not None
    with pytest.raises(HomeAssistantError, match=user_error):
        await hass.services.async_call(
            "time",
            SERVICE_SET_VALUE,
            service_data={"time": time(hour=7, minute=0)},
            blocking=True,
            target={"entity_id": "time.garden_light_on"},
        )
