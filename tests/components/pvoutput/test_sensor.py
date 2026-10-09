"""Tests for the sensors provided by the PVOutput integration."""

import dataclasses
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pvoutput.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

OPTIONAL_SENSOR_KEYS = (
    "energy_consumption",
    "power_consumption",
    "temperature",
    "voltage",
)


def _unique_ids(
    entity_registry: er.EntityRegistry, config_entry: MockConfigEntry
) -> set[str]:
    """Return the unique IDs of all entities of the config entry."""
    return {
        entity_entry.unique_id
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the PVOutput sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.frenck_s_solar_farm_temperature",
        "sensor.frenck_s_solar_farm_voltage",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> None:
    """Test the PVOutput sensors that are disabled by default."""
    assert not hass.states.get(entity_id)

    assert (entity_entry := entity_registry.async_get(entity_id))
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("init_integration")
async def test_device(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the PVOutput device."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12345"), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot

    # The entity snapshots mask the device ID, so check the link explicitly
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entity_entry.device_id for entity_entry in entity_entries} == {
        device_entry.id
    }


@pytest.mark.parametrize("key", OPTIONAL_SENSOR_KEYS)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_optional_sensor_added_once_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_pvoutput: MagicMock,
    key: str,
) -> None:
    """Test an optional sensor is only added once the system reports it."""
    status = mock_pvoutput.status.return_value
    mock_pvoutput.status.return_value = dataclasses.replace(
        status, **dict.fromkeys(OPTIONAL_SENSOR_KEYS)
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    core_unique_ids = {
        "12345_energy_generation",
        "12345_normalized_output",
        "12345_power_generation",
    }
    assert _unique_ids(entity_registry, mock_config_entry) == core_unique_ids

    # An update without the optional values does not add anything
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _unique_ids(entity_registry, mock_config_entry) == core_unique_ids

    # Only this sensor reports a value, so only this sensor is added
    mock_pvoutput.status.return_value = dataclasses.replace(
        status, **{**dict.fromkeys(OPTIONAL_SENSOR_KEYS), key: getattr(status, key)}
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _unique_ids(entity_registry, mock_config_entry) == core_unique_ids | {
        f"12345_{key}"
    }

    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"12345_{key}"
    )
    assert entity_id
    assert (state := hass.states.get(entity_id))
    assert float(state.state) == getattr(status, key)


async def test_optional_sensors_kept_when_registered(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pvoutput: MagicMock,
) -> None:
    """Test existing optional sensors are kept, even without a value."""
    mock_pvoutput.status.return_value = dataclasses.replace(
        mock_pvoutput.status.return_value, **dict.fromkeys(OPTIONAL_SENSOR_KEYS)
    )

    mock_config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "12345_energy_consumption",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == STATE_UNKNOWN
