"""Tests for 1-Wire sensors."""

from collections.abc import Generator
from copy import deepcopy
import logging
from unittest.mock import MagicMock, _patch_dict, patch

from pyownet.protocol import OwnetError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_owproxy_mock_devices
from .const import ATTR_INJECT_READS, MOCK_OWPROXY_DEVICES


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire.PLATFORMS", [Platform.SENSOR]):
        yield


async def test_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
    device_id: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for 1-Wire sensors."""
    setup_owproxy_mock_devices(owproxy, Platform.SENSOR, [device_id])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure devices are correctly registered
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert device_entries == snapshot

    # Ensure entities are correctly registered
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == snapshot

    setup_owproxy_mock_devices(owproxy, Platform.SENSOR, [device_id])
    # Some entities are disabled, enable them and reload before checking states
    for ent in entity_entries:
        entity_registry.async_update_entity(ent.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure entity states are correct
    states = [hass.states.get(ent.entity_id) for ent in entity_entries]
    assert states == snapshot


@pytest.mark.parametrize("device_id", ["12.111111111111"])
async def test_tai8570_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
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
    mock_device[ATTR_INJECT_READS].append(OwnetError)
    mock_device[ATTR_INJECT_READS].append(OwnetError)

    with _patch_dict(MOCK_OWPROXY_DEVICES, mock_devices):
        setup_owproxy_mock_devices(owproxy, Platform.SENSOR, [device_id])

    with caplog.at_level(logging.DEBUG):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.entities.get("sensor.12_111111111111_temperature") is None
    assert "unreachable sensor /12.111111111111/TAI8570/temperature" in caplog.text

    assert entity_registry.entities.get("sensor.12_111111111111_pressure") is None
    assert "unreachable sensor /12.111111111111/TAI8570/pressure" in caplog.text
