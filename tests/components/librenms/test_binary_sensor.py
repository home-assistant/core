"""Test the LibreNMS binary sensor platform."""

from unittest.mock import Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_librenms: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the LibreNMS binary sensor platform."""

    with patch("homeassistant.components.librenms.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    dev_reg = dr.async_get(hass)
    devices = dev_reg.devices.get_devices_for_config_entry_id(
        mock_config_entry.entry_id
    )
    assert devices == snapshot
