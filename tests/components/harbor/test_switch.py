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
VIDEO_FLIP_ENTITY = "switch.harbor_camera_1234567890_flip_image"
CLOCK_DISPLAY_ENTITY = "switch.harbor_camera_1234567890_clock_overlay"


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


@pytest.mark.parametrize(
    ("entity_id", "library_method"),
    [
        pytest.param(CAMERA_ON_ENTITY, "set_camera_on", id="camera_on"),
        pytest.param(VIDEO_FLIP_ENTITY, "set_video_flip", id="video_flip"),
        pytest.param(CLOCK_DISPLAY_ENTITY, "set_clock_display", id="clock_display"),
    ],
)
async def test_turn_on_and_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
    entity_id: str,
    library_method: str,
) -> None:
    """Test turning each switch on and off calls the library."""
    await setup_integration(hass, mock_config_entry)
    mock_method = getattr(mock_mqtt_client.return_value, library_method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_method.assert_awaited_once_with(True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_method.assert_awaited_with(False)


@pytest.mark.parametrize(
    ("entity_id", "library_method", "command"),
    [
        pytest.param(
            CAMERA_ON_ENTITY, "set_camera_on", "unpause-stream", id="camera_on"
        ),
        pytest.param(
            VIDEO_FLIP_ENTITY, "set_video_flip", "update-settings", id="video_flip"
        ),
        pytest.param(
            CLOCK_DISPLAY_ENTITY,
            "set_clock_display",
            "update-settings",
            id="clock_display",
        ),
    ],
)
async def test_turn_on_failure_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
    entity_id: str,
    library_method: str,
    command: str,
) -> None:
    """Test a command rejection from the camera surfaces as a HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    getattr(
        mock_mqtt_client.return_value, library_method
    ).side_effect = HarborCommandError(command, {"error": "rejected"})

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
