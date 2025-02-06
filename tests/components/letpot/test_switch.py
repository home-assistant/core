"""Test switch entities for the LetPot integration."""

from unittest.mock import MagicMock

from letpot.exceptions import LetPotConnectionException, LetPotException
import pytest

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("service", "exception", "user_error"),
    [
        (
            SERVICE_TURN_ON,
            LetPotConnectionException("Connection failed"),
            "An error occurred while communicating with the LetPot device: Connection failed",
        ),
        (
            SERVICE_TURN_OFF,
            LetPotException("Random thing failed"),
            "An unknown error occurred while communicating with the LetPot device: Random thing failed",
        ),
    ],
)
async def test_switch_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    service: str,
    exception: Exception,
    user_error: str,
) -> None:
    """Test switch entity exception handling."""
    await setup_integration(hass, mock_config_entry)

    mock_device_client.set_power.side_effect = exception

    assert hass.states.get("switch.garden_power") is not None
    with pytest.raises(HomeAssistantError, match=user_error):
        await hass.services.async_call(
            "switch",
            service,
            blocking=True,
            target={"entity_id": "switch.garden_power"},
        )
