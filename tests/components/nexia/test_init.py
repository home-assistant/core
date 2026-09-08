"""The init tests for the nexia platform."""

from unittest.mock import NonCallableMock, patch

import aiohttp
from nexia.home import NexiaHome
import pytest

from homeassistant.components.nexia import _preregister_devices
from homeassistant.components.nexia.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from .conftest import setup_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_setup_retry_client_os_error(
    hass: HomeAssistant,
    patch_nexia_home: NonCallableMock[NexiaHome],
) -> None:
    """Verify we retry setup on aiohttp.ClientOSError."""

    patch_nexia_home.login.side_effect = aiohttp.ClientOSError
    config_entry = await setup_integration(hass, patch_nexia_home)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_remove_devices(
    hass: HomeAssistant,
    patch_nexia_home: NexiaHome,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we can only remove a device that no longer exists."""
    await async_setup_component(hass, "config", {})
    config_entry = await setup_integration(hass, patch_nexia_home)
    client = await hass_ws_client(hass)

    entity = entity_registry.entities["sensor.upstairs_upstairs_roomiq_temperature"]
    live_room_iq_device_entry = device_registry.async_get(entity.device_id)
    response = await client.remove_device(live_room_iq_device_entry.id)
    assert not response["success"]

    entity = entity_registry.entities["sensor.nick_office_nick_office_temperature"]
    live_zone_device_entry = device_registry.async_get(entity.device_id)
    response = await client.remove_device(live_zone_device_entry.id)
    assert not response["success"]

    entity = entity_registry.entities["sensor.master_suite_humidity"]
    live_thermostat_device_entry = device_registry.async_get(entity.device_id)
    response = await client.remove_device(live_thermostat_device_entry.id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "unused")},
    )
    response = await client.remove_device(dead_device_entry.id)
    assert response["success"]


async def test_migrate_entry_minor_version_1_2(hass: HomeAssistant) -> None:
    """Test migrating a 1.1 config entry to 1.2."""
    with patch("homeassistant.components.nexia.async_setup_entry", return_value=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"},
            version=1,
            minor_version=1,
            unique_id=123456,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 1
        assert entry.minor_version == 2
        assert entry.unique_id == "123456"


@pytest.mark.usefixtures("patch_nexia_home")
async def test_migrate_entity_identifiers(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test migrating config entity identifiers to string."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"}
    )
    entry.add_to_hass(hass)

    int_entry = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        85034552,
        config_entry=entry,
    )
    str_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "already_a_string",
        config_entry=entry,
    )
    modified_before = str_entry.modified_at
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    migrated_entry = entity_registry.async_get(int_entry.entity_id)
    assert migrated_entry is not None
    assert migrated_entry.unique_id == "85034552"
    assert migrated_entry.entity_id == int_entry.entity_id

    unchanged_entry = entity_registry.async_get(str_entry.entity_id)
    assert unchanged_entry is not None
    assert unchanged_entry.unique_id == "already_a_string"
    assert unchanged_entry.modified_at == modified_before


@pytest.mark.usefixtures("patch_nexia_home")
async def test_migrate_device_identifiers(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test migrating config device identifiers to string."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"}
    )
    entry.add_to_hass(hass)

    int_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, 12345), ("other_domain", "not_touched")},
        name="Center",
    )
    str_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "already_a_string")},
        name="Center",
    )
    modified_before = str_device.modified_at
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    migrated_device = device_registry.async_get(int_device.id)
    assert migrated_device is not None
    assert migrated_device.identifiers == {
        (DOMAIN, "12345"),
        ("other_domain", "not_touched"),
    }
    assert migrated_device.id == int_device.id

    unchanged_device = device_registry.async_get(str_device.id)
    assert unchanged_device is not None
    assert unchanged_device.identifiers == {(DOMAIN, "already_a_string")}
    assert unchanged_device.modified_at == modified_before


async def test_string_identifiers(
    hass: HomeAssistant,
    patch_nexia_home: NexiaHome,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the identifiers are strings."""
    entry = await setup_integration(hass, patch_nexia_home)

    entities = entity_registry.entities
    entity_entries = entities.get_entries_for_config_entry_id(entry.entry_id)
    assert len(entity_entries) > 0
    for entity_entry in entity_entries:
        assert isinstance(entity_entry.unique_id, str)

    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(device_entries) > 0
    for device_entry in device_entries:
        for domain, ident in device_entry.identifiers:
            assert isinstance(ident, str), (
                f"Device [{device_entry.name}] has non-string identifier ({domain}, {ident})"
            )


async def test_device_preregistration(
    hass: HomeAssistant, mock_nexia_home: NexiaHome, device_registry: dr.DeviceRegistry
) -> None:
    """Test all thermostat and zone devices are preregistered."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    _preregister_devices(device_registry, entry, mock_nexia_home)

    thermostat_ids = mock_nexia_home.get_thermostat_ids()
    assert len(thermostat_ids) > 0

    for thermostat_id in thermostat_ids:
        thermostat = mock_nexia_home.get_thermostat_by_id(thermostat_id)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, str(thermostat.thermostat_id)), entry.entry_id
        )
        assert device is not None

        zone_ids = thermostat.get_zone_ids()
        assert len(zone_ids) > 0

        for zone_id in zone_ids:
            zone = thermostat.get_zone_by_id(zone_id)
            device = device_registry.async_get_device_by_identifier(
                (DOMAIN, str(zone.zone_id)), entry.entry_id
            )
            assert device is not None
            assert device.area_id == slugify(zone.get_name())


async def test_device_via_device_links(
    hass: HomeAssistant,
    patch_nexia_home: NexiaHome,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a zone device links to its thermostat via via_device_id."""
    config_entry = await setup_integration(hass, patch_nexia_home)

    thermostat_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "2000004"), config_entry.entry_id
    )
    assert thermostat_device is not None

    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "500"), config_entry.entry_id
    )
    assert zone_device is not None
    assert zone_device.via_device_id == thermostat_device.id
    assert zone_device.area_id == "zone3"

    sensor_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "502"), config_entry.entry_id
    )
    assert sensor_device is not None
    assert sensor_device.via_device_id == zone_device.id
    assert sensor_device.area_id == "upstairs"
