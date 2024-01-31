"""Test init of GIOS integration."""
import json
from unittest.mock import patch

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.components.gios.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import STATIONS, init_integration

from tests.common import MockConfigEntry, load_fixture


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("sensor.home_pm2_5")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "4"


async def test_config_not_ready(hass: HomeAssistant) -> None:
    """Test for setup failure if connection to GIOS is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id=123,
        data={"station_id": 123, "name": "Home"},
    )

    with patch(
        "homeassistant.components.gios.Gios._get_stations",
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
        data={
            "station_id": 123,
            "name": "Home",
        },
    )

    indexes = json.loads(load_fixture("gios/indexes.json"))
    station = json.loads(load_fixture("gios/station.json"))
    sensors = json.loads(load_fixture("gios/sensors.json"))

    with patch(
        "homeassistant.components.gios.Gios._get_stations", return_value=STATIONS
    ), patch(
        "homeassistant.components.gios.Gios._get_station",
        return_value=station,
    ), patch(
        "homeassistant.components.gios.Gios._get_all_sensors",
        return_value=sensors,
    ), patch("homeassistant.components.gios.Gios._get_indexes", return_value=indexes):
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
        suggested_object_id="home",
        disabled_by=None,
    )

    await init_integration(hass)

    entry = entity_registry.async_get("air_quality.home")
    assert entry is None
