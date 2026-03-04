"""Test sensor platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nintendo_parental_controls.sensor import (
    PLAYER_SENSOR_DESCRIPTIONS,
    NintendoParentalControlsPlayerSensorEntity,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor platform."""
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_player_sensor_none_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
) -> None:
    """Test player sensor returns None when player is not in device players."""
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    # Get the coordinator and device from runtime data
    coordinator = mock_config_entry.runtime_data
    device = coordinator.api.devices["testdevid"]

    # Create a sensor entity with the first player sensor description
    sensor = NintendoParentalControlsPlayerSensorEntity(
        coordinator=coordinator,
        device=device,
        player="testplayerid",
        description=PLAYER_SENSOR_DESCRIPTIONS[0],
    )

    # Verify entity_picture and native_value work normally
    assert sensor.entity_picture is not None
    assert sensor.native_value is not None

    # Remove player from device and verify None is returned
    device.players = {}
    assert sensor.entity_picture is None
    assert sensor.native_value is None
