"""Tests for 1-Wire sensors."""

from collections.abc import Generator
from copy import deepcopy
import logging
from unittest.mock import MagicMock, _patch_dict, patch

from freezegun.api import FrozenDateTimeFactory
from pyownet.protocol import OwnetError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.onewire.onewirehub import _DEVICE_SCAN_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_owproxy_mock_devices
from .const import ATTR_INJECT_READS, MOCK_OWPROXY_DEVICES

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire._PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for 1-Wire sensor entities."""
    setup_owproxy_mock_devices(owproxy, MOCK_OWPROXY_DEVICES.keys())
    await hass.config_entries.async_setup(config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("device_id", ["12.111111111111"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_delayed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    device_id: str,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for delayed 1-Wire sensor entities."""
    setup_owproxy_mock_devices(owproxy, [])
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)

    setup_owproxy_mock_devices(owproxy, [device_id])
    freezer.tick(_DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        len(er.async_entries_for_config_entry(entity_registry, config_entry.entry_id))
        == 2
    )


@pytest.mark.parametrize("device_id", ["12.111111111111"])
async def test_tai8570_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    device_id: str,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The DS2602 is often used without TAI8570.

    The sensors should be ignored.
    """
    mock_devices = deepcopy(MOCK_OWPROXY_DEVICES)
    mock_device = mock_devices[device_id]
    mock_device[ATTR_INJECT_READS]["/TAI8570/temperature"] = [OwnetError]
    mock_device[ATTR_INJECT_READS]["/TAI8570/pressure"] = [OwnetError]

    with _patch_dict(MOCK_OWPROXY_DEVICES, mock_devices):
        setup_owproxy_mock_devices(owproxy, [device_id])

    with caplog.at_level(logging.DEBUG):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.entities.get("sensor.12_111111111111_temperature") is None
    assert "unreachable sensor /12.111111111111/TAI8570/temperature" in caplog.text

    assert entity_registry.entities.get("sensor.12_111111111111_pressure") is None
    assert "unreachable sensor /12.111111111111/TAI8570/pressure" in caplog.text
