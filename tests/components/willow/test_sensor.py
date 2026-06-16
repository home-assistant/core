"""Tests for the Willow sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "sensor.kitchen_basil_temperature"


@pytest.mark.usefixtures("mock_willow_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every Willow sensor entity."""
    with patch("homeassistant.components.willow._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_unavailable_without_reading(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A reading sensor is unavailable when the device has no latest reading."""
    devices = mock_willow_client.get_devices.return_value
    devices[0]["latest_reading"] = None

    with patch("homeassistant.components.willow._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
