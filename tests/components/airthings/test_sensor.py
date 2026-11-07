"""Test the Airthings sensors."""

from dataclasses import replace
import logging

from airthings import Airthings, AirthingsDevice, AirthingsError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airthings.const import DOMAIN
from homeassistant.components.airthings.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


async def _async_refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _entity_ids(
    entity_registry: er.EntityRegistry, entry: MockConfigEntry, device_id: str
) -> list[str]:
    return [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if entity.unique_id.startswith(f"{device_id}_") and not entity.disabled_by
    ]


async def test_all_device_types(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_airthings_client: Airthings,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all device types."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("airthings_fixture", ["wave_plus"])
async def test_sensors_unavailable_when_device_is_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airthings_client: Airthings,
    mock_airthings_device: AirthingsDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test only the missing device's sensors become unavailable."""
    other_device = replace(
        mock_airthings_device, device_id="2930000003", name="Bedroom"
    )
    mock_airthings_client.update_devices.return_value = {
        mock_airthings_device.device_id: mock_airthings_device,
        other_device.device_id: other_device,
    }
    await setup_integration(hass, mock_config_entry)
    missing_ids = _entity_ids(
        entity_registry, mock_config_entry, mock_airthings_device.device_id
    )
    other_ids = _entity_ids(entity_registry, mock_config_entry, other_device.device_id)
    assert missing_ids
    assert other_ids
    initial = {entity_id: hass.states.get(entity_id).state for entity_id in missing_ids}
    assert STATE_UNAVAILABLE not in initial.values()

    mock_airthings_client.update_devices.return_value = {
        other_device.device_id: other_device
    }
    await _async_refresh(hass, freezer)

    for entity_id in missing_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    for entity_id in other_ids:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]

    mock_airthings_client.update_devices.return_value = {
        mock_airthings_device.device_id: mock_airthings_device,
        other_device.device_id: other_device,
    }
    await _async_refresh(hass, freezer)

    assert {
        entity_id: hass.states.get(entity_id).state for entity_id in missing_ids
    } == initial


@pytest.mark.parametrize("airthings_fixture", ["wave_plus"])
async def test_sensor_unavailable_when_value_is_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airthings_client: Airthings,
    mock_airthings_device: AirthingsDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor becomes unavailable when the device stops reporting it."""
    await setup_integration(hass, mock_config_entry)
    co2_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{mock_airthings_device.device_id}_co2"
    )
    temp_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{mock_airthings_device.device_id}_temp"
    )
    assert co2_id
    assert temp_id
    assert hass.states.get(co2_id).state == "2.2"

    sensors = dict(mock_airthings_device.sensors)
    del sensors["co2"]
    mock_airthings_client.update_devices.return_value = {
        mock_airthings_device.device_id: replace(mock_airthings_device, sensors=sensors)
    }
    await _async_refresh(hass, freezer)

    assert hass.states.get(co2_id).state == STATE_UNAVAILABLE
    assert hass.states.get(temp_id).state == "6.6"


@pytest.mark.parametrize("airthings_fixture", ["wave_plus"])
async def test_sensors_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airthings_client: Airthings,
    mock_airthings_device: AirthingsDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable when fetching fails and recover after."""
    await setup_integration(hass, mock_config_entry)
    entity_ids = _entity_ids(
        entity_registry, mock_config_entry, mock_airthings_device.device_id
    )
    assert entity_ids
    initial = {entity_id: hass.states.get(entity_id).state for entity_id in entity_ids}
    assert STATE_UNAVAILABLE not in initial.values()

    mock_airthings_client.update_devices.side_effect = AirthingsError("boom")
    await _async_refresh(hass, freezer)

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_airthings_client.update_devices.side_effect = None
    await _async_refresh(hass, freezer)

    assert {
        entity_id: hass.states.get(entity_id).state for entity_id in entity_ids
    } == initial
