"""Tests for the Minecraft Server integration."""
from unittest.mock import patch

import aiodns

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.minecraft_server.const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import TEST_HOST, TEST_JAVA_STATUS_RESPONSE

from tests.common import MockConfigEntry

TEST_UNIQUE_ID = f"{TEST_HOST}-{DEFAULT_PORT}"

SENSOR_KEYS = [
    {"v1": "Latency Time", "v2": "latency"},
    {"v1": "Players Max", "v2": "players_max"},
    {"v1": "Players Online", "v2": "players_online"},
    {"v1": "Protocol Version", "v2": "protocol_version"},
    {"v1": "Version", "v2": "version"},
    {"v1": "World Message", "v2": "motd"},
]

BINARY_SENSOR_KEYS = {"v1": "Status", "v2": "status"}


async def test_entry_migration_v1_to_v2(hass: HomeAssistant) -> None:
    """Test entry migratiion from version 1 to 2."""

    # Create mock config entry.
    config_entry_v1 = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_HOST: TEST_HOST,
            CONF_PORT: DEFAULT_PORT,
        },
        version=1,
    )
    config_entry_id = config_entry_v1.entry_id
    config_entry_v1.add_to_hass(hass)

    # Create mock device entry.
    device_registry = dr.async_get(hass)
    device_entry_v1 = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, TEST_UNIQUE_ID)},
    )
    device_entry_id = device_entry_v1.id
    assert device_entry_v1
    assert device_entry_id

    # Create mock sensor entity entries.
    sensor_entity_id_key_mapping_list = []
    entity_registry = er.async_get(hass)
    for sensor_key in SENSOR_KEYS:
        entity_unique_id = f"{TEST_UNIQUE_ID}-{sensor_key['v1']}"
        entity_entry_v1 = entity_registry.async_get_or_create(
            SENSOR_DOMAIN,
            DOMAIN,
            unique_id=entity_unique_id,
            config_entry=config_entry_v1,
            device_id=device_entry_id,
        )
        assert entity_entry_v1.unique_id == entity_unique_id
        sensor_entity_id_key_mapping_list.append(
            {"entity_id": entity_entry_v1.entity_id, "key": sensor_key["v2"]}
        )

    # Create mock binary sensor entity entry.
    entity_unique_id = f"{TEST_UNIQUE_ID}-{BINARY_SENSOR_KEYS['v1']}"
    entity_entry_v1 = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        unique_id=entity_unique_id,
        config_entry=config_entry_v1,
        device_id=device_entry_id,
    )
    assert entity_entry_v1.unique_id == entity_unique_id
    binary_sensor_entity_id_key_mapping = {
        "entity_id": entity_entry_v1.entity_id,
        "key": BINARY_SENSOR_KEYS["v2"],
    }

    # Trigger migration.
    with patch(
        "aiodns.DNSResolver.query",
        side_effect=aiodns.error.DNSError,
    ), patch(
        "mcstatus.server.JavaServer.async_status",
        return_value=TEST_JAVA_STATUS_RESPONSE,
    ):
        assert await hass.config_entries.async_setup(config_entry_id)
        await hass.async_block_till_done()

    # Test migrated config entry.
    config_entry_v2 = hass.config_entries.async_get_entry(config_entry_id)
    assert config_entry_v2.unique_id is None
    assert config_entry_v2.data == {
        CONF_NAME: DEFAULT_NAME,
        CONF_HOST: TEST_HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    assert config_entry_v2.version == 2

    # Test migrated device entry.
    device_entry_v2 = device_registry.async_get(device_entry_id)
    assert device_entry_v2.identifiers == {(DOMAIN, config_entry_id)}

    # Test migrated sensor entity entries.
    for mapping in sensor_entity_id_key_mapping_list:
        entity_entry_v2 = entity_registry.async_get(mapping["entity_id"])
        assert entity_entry_v2.unique_id == f"{config_entry_id}-{mapping['key']}"

    # Test migrated binary sensor entity entry.
    entity_entry_v2 = entity_registry.async_get(
        binary_sensor_entity_id_key_mapping["entity_id"]
    )
    assert (
        entity_entry_v2.unique_id
        == f"{config_entry_id}-{binary_sensor_entity_id_key_mapping['key']}"
    )
