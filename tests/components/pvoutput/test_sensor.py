"""Tests for the sensors provided by the PVOutput integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pvoutput.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("init_integration")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the PVOutput sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_device(
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the PVOutput device."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12345"), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot
