"""Tests for Midea binary_sensor.py."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary_sensor entities are created."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.comfort_mode: False,
            ACAttributes.eco_mode: False,
            ACAttributes.boost_mode: False,
            ACAttributes.sleep_mode: False,
            ACAttributes.frost_protect: False,
            ACAttributes.fan_speed: 103,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
            ACAttributes.indoor_humidity: 50,
            ACAttributes.full_dust: True,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, config_entry, device)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_binary_sensor_state_update(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    set_device_attribute: Callable[
        [DummyDevice, str, object], Coroutine[Any, Any, None]
    ],
) -> None:
    """Test binary_sensor state follows push updates from the device."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.full_dust: False,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_full_dust"]

    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == "off"

    await set_device_attribute(device, ACAttributes.full_dust, True)

    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == "on"
