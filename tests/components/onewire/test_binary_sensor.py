"""Tests for 1-Wire binary sensors."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.onewire.onewirehub import _DEVICE_SCAN_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_owproxy_mock_devices
from .const import MOCK_OWPROXY_DEVICES

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire._PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for 1-Wire binary sensor entities."""
    setup_owproxy_mock_devices(owproxy, MOCK_OWPROXY_DEVICES.keys())
    await hass.config_entries.async_setup(config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("device_id", ["29.111111111111"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors_delayed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    device_id: str,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for delayed 1-Wire binary sensor entities."""
    setup_owproxy_mock_devices(owproxy, [])
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)

    setup_owproxy_mock_devices(owproxy, [device_id])
    freezer.tick(_DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        len(er.async_entries_for_config_entry(entity_registry, config_entry.entry_id))
        == 8
    )
