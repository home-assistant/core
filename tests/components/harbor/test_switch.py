"""Test the Harbor switches."""

from unittest.mock import AsyncMock, patch

from harbor import HarborCommandError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import SETTINGS_PAYLOAD, SETTINGS_TOPIC, emit_message

from tests.common import MockConfigEntry, snapshot_platform

CAMERA_ON_ENTITY = "switch.harbor_camera_1234567890_camera"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Harbor switches report their state."""
    with patch("homeassistant.components.harbor.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await emit_message(mock_mqtt_client, SETTINGS_TOPIC, SETTINGS_PAYLOAD)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_camera_on_and_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test turning the camera switch on and off calls the library."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: CAMERA_ON_ENTITY},
        blocking=True,
    )
    mock_mqtt_client.return_value.set_camera_on.assert_awaited_once_with(True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: CAMERA_ON_ENTITY},
        blocking=True,
    )
    mock_mqtt_client.return_value.set_camera_on.assert_awaited_with(False)


async def test_turn_on_failure_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test a command rejection from the camera surfaces as a HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    mock_mqtt_client.return_value.set_camera_on.side_effect = HarborCommandError(
        "unpause-stream", {"error": "rejected"}
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: CAMERA_ON_ENTITY},
            blocking=True,
        )
