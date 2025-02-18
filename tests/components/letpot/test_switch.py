"""Test switch entities for the LetPot integration."""

from unittest.mock import MagicMock, patch

from letpot.exceptions import LetPotConnectionException, LetPotException
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.switch import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch entities."""
    with patch("homeassistant.components.letpot.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "parameter_value"),
    [
        (
            SERVICE_TURN_ON,
            True,
        ),
        (
            SERVICE_TURN_OFF,
            False,
        ),
        (
            SERVICE_TOGGLE,
            False,  # Mock switch is on after setup, toggle will turn off
        ),
    ],
)
async def test_set_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    service: str,
    parameter_value: bool,
) -> None:
    """Test switch entity turned on/turned off/toggled."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "switch",
        service,
        blocking=True,
        target={"entity_id": "switch.garden_power"},
    )

    mock_device_client.set_power.assert_awaited_once_with(parameter_value)


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
