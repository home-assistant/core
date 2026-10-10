"""Tests for Fritz!Tools device tracker platform."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.freeze_time(datetime(2026, 8, 18, 20, tzinfo=UTC))
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of Fritz!Tools device_tracker."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.DEVICE_TRACKER]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)

    for device in device_registry.devices.values():
        assert device == snapshot(name=f"{device.name}-device")
