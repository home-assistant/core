"""Test init of GIOS integration."""

import json
from unittest.mock import patch

import pytest

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.components.gios.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import STATIONS, init_integration

from tests.common import (
    MockConfigEntry,
    async_load_fixture,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
)


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("sensor.station_test_name_1_pm2_5")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "4"


async def test_config_not_ready(hass: HomeAssistant) -> None:
    """Test for setup failure if connection to GIOS is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id=123,
        data={"station_id": 123},
        version=2,
    )

    with patch(
        "homeassistant.components.gios.coordinator.Gios._get_stations",
        side_effect=ConnectionError(),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_migrate_device_and_config_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test device_info identifiers and config entry migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id=123,
        data={"station_id": 123},
        version=2,
    )

    indexes = json.loads(await async_load_fixture(hass, "indexes.json", DOMAIN))
    station = json.loads(await async_load_fixture(hass, "station.json", DOMAIN))
    sensors = json.loads(await async_load_fixture(hass, "sensors.json", DOMAIN))

    with (
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_stations",
            return_value=STATIONS,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_station",
            return_value=station,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_all_sensors",
            return_value=sensors,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_indexes",
            return_value=indexes,
        ),
    ):
        config_entry.add_to_hass(hass)

        device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, 123)}
        )

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        migrated_device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "123")}
        )
        assert device_entry.id == migrated_device_entry.id


async def test_remove_air_quality_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test remove air_quality entities from registry."""
    entity_registry.async_get_or_create(
        AIR_QUALITY_PLATFORM,
        DOMAIN,
        "123",
        suggested_object_id="station_test_name_1",
        disabled_by=None,
    )

    await init_integration(hass)

    entry = entity_registry.async_get("air_quality.station_test_name_1")
    assert entry is None


@pytest.mark.parametrize(
    ("device_name_by_user", "expected_device_name"),
    [
        (None, "Home"),
        ("Custom device name", "Custom device name"),
    ],
)
async def test_migrate_config_entry_from_1_to_2(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    device_name_by_user,
    expected_device_name,
) -> None:
    """Test migrate to newest version."""
    station_id = 123
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="123",
        data={"station_id": station_id, "name": "Home"},
        entry_id="86129426118ae32020417a53712d6eef",
        version=1,
    )

    indexes = await async_load_json_object_fixture(hass, "indexes.json", DOMAIN)
    station = await async_load_json_array_fixture(hass, "station.json", DOMAIN)
    sensors = await async_load_json_object_fixture(hass, "sensors.json", DOMAIN)

    with (
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_stations",
            return_value=STATIONS,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_station",
            return_value=station,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_all_sensors",
            return_value=sensors,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_indexes",
            return_value=indexes,
        ),
    ):
        entry.add_to_hass(hass)
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={(DOMAIN, str(station_id))}
        )
        if device_name_by_user is not None:
            device_registry.async_update_device(
                device_id=device.id, name_by_user=device_name_by_user
            )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        assert len(devices) == 1
        device = devices[0]

        assert device.name == "Station Test Name 1"
        assert device.name_by_user == expected_device_name
