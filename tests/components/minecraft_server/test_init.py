"""Tests for the Minecraft Server integration."""

from unittest.mock import patch

from mcstatus import JavaServer
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.minecraft_server.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    TEST_ADDRESS,
    TEST_CONFIG_ENTRY_ID,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_PORT,
)

from tests.common import MockConfigEntry

DEFAULT_NAME = "Minecraft Server"

TEST_UNIQUE_ID = f"{TEST_HOST}-{TEST_PORT}"

SENSOR_KEYS = [
    {"v1": "Latency Time", "v2": "latency"},
    {"v1": "Players Max", "v2": "players_max"},
    {"v1": "Players Online", "v2": "players_online"},
    {"v1": "Protocol Version", "v2": "protocol_version"},
    {"v1": "Version", "v2": "version"},
    {"v1": "World Message", "v2": "motd"},
]

BINARY_SENSOR_KEYS = {"v1": "Status", "v2": "status"}


@pytest.fixture
def v1_mock_config_entry() -> MockConfigEntry:
    """Create mock config entry with version 1."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        entry_id=TEST_CONFIG_ENTRY_ID,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
        },
        version=1,
    )


def create_v1_mock_device_entry(hass: HomeAssistant, config_entry_id: str) -> str:
    """Create mock device entry with version 1."""
    device_registry = dr.async_get(hass)
    device_entry_v1 = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, TEST_UNIQUE_ID)},
    )
    device_entry_id = device_entry_v1.id

    assert device_entry_v1
    assert device_entry_id

    return device_entry_id


def create_v1_mock_sensor_entity_entries(
    hass: HomeAssistant, config_entry_id: str, device_entry_id: str
) -> list[dict]:
    """Create mock sensor entity entries with version 1."""
    sensor_entity_id_key_mapping_list = []
    config_entry = hass.config_entries.async_get_entry(config_entry_id)
    entity_registry = er.async_get(hass)

    for sensor_key in SENSOR_KEYS:
        entity_unique_id = f"{TEST_UNIQUE_ID}-{sensor_key['v1']}"
        entity_entry_v1 = entity_registry.async_get_or_create(
            SENSOR_DOMAIN,
            DOMAIN,
            unique_id=entity_unique_id,
            config_entry=config_entry,
            device_id=device_entry_id,
        )
        assert entity_entry_v1.unique_id == entity_unique_id
        sensor_entity_id_key_mapping_list.append(
            {"entity_id": entity_entry_v1.entity_id, "key": sensor_key["v2"]}
        )

    return sensor_entity_id_key_mapping_list


def create_v1_mock_binary_sensor_entity_entry(
    hass: HomeAssistant, config_entry_id: str, device_entry_id: str
) -> dict:
    """Create mock binary sensor entity entry with version 1."""
    config_entry = hass.config_entries.async_get_entry(config_entry_id)
    entity_registry = er.async_get(hass)
    entity_unique_id = f"{TEST_UNIQUE_ID}-{BINARY_SENSOR_KEYS['v1']}"
    entity_entry = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        unique_id=entity_unique_id,
        config_entry=config_entry,
        device_id=device_entry_id,
    )
    assert entity_entry.unique_id == entity_unique_id
    return {
        "entity_id": entity_entry.entity_id,
        "key": BINARY_SENSOR_KEYS["v2"],
    }


async def test_setup_and_unload_entry(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test successful entry setup and unload."""
    java_mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(java_mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert java_mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(java_mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)
    assert java_mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_lookup_failure(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test lookup failure in entry setup."""
    java_mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
        side_effect=ValueError,
    ):
        assert not await hass.config_entries.async_setup(
            java_mock_config_entry.entry_id
        )

    await hass.async_block_till_done()
    assert java_mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_init_failure(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test init failure in entry setup."""
    java_mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.async_initialize",
        side_effect=None,
    ):
        assert not await hass.config_entries.async_setup(
            java_mock_config_entry.entry_id
        )

    await hass.async_block_till_done()
    assert java_mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_not_ready(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test entry setup not ready."""
    java_mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=OSError,
        ),
    ):
        assert not await hass.config_entries.async_setup(
            java_mock_config_entry.entry_id
        )

    await hass.async_block_till_done()
    assert java_mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_entry_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    v1_mock_config_entry: MockConfigEntry,
) -> None:
    """Test entry migration from version 1 to 3, where host and port is required for the connection to the server."""
    v1_mock_config_entry.add_to_hass(hass)

    device_entry_id = create_v1_mock_device_entry(hass, v1_mock_config_entry.entry_id)
    sensor_entity_id_key_mapping_list = create_v1_mock_sensor_entity_entries(
        hass, v1_mock_config_entry.entry_id, device_entry_id
    )
    binary_sensor_entity_id_key_mapping = create_v1_mock_binary_sensor_entity_entry(
        hass, v1_mock_config_entry.entry_id, device_entry_id
    )

    # Trigger migration.
    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            side_effect=[
                ValueError,  # async_migrate_entry
                JavaServer(host=TEST_HOST, port=TEST_PORT),  # async_migrate_entry
                JavaServer(host=TEST_HOST, port=TEST_PORT),  # async_setup_entry
            ],
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(v1_mock_config_entry.entry_id)
        await hass.async_block_till_done()

    migrated_config_entry = v1_mock_config_entry

    # Test migrated config entry.
    assert migrated_config_entry.unique_id is None
    assert migrated_config_entry.data == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ADDRESS: TEST_ADDRESS,
    }
    assert migrated_config_entry.version == 3
    assert migrated_config_entry.state is ConfigEntryState.LOADED

    # Test migrated device entry.
    device_entry = device_registry.async_get(device_entry_id)
    assert device_entry.identifiers == {(DOMAIN, migrated_config_entry.entry_id)}

    # Test migrated sensor entity entries.
    for mapping in sensor_entity_id_key_mapping_list:
        entity_entry = entity_registry.async_get(mapping["entity_id"])
        assert (
            entity_entry.unique_id
            == f"{migrated_config_entry.entry_id}-{mapping['key']}"
        )

    # Test migrated binary sensor entity entry.
    entity_entry = entity_registry.async_get(
        binary_sensor_entity_id_key_mapping["entity_id"]
    )
    assert (
        entity_entry.unique_id
        == f"{migrated_config_entry.entry_id}-{binary_sensor_entity_id_key_mapping['key']}"
    )


async def test_entry_migration_host_only(
    hass: HomeAssistant, v1_mock_config_entry: MockConfigEntry
) -> None:
    """Test entry migration from version 1 to 3, where host alone is sufficient for the connection to the server."""
    v1_mock_config_entry.add_to_hass(hass)

    device_entry_id = create_v1_mock_device_entry(hass, v1_mock_config_entry.entry_id)
    create_v1_mock_sensor_entity_entries(
        hass, v1_mock_config_entry.entry_id, device_entry_id
    )
    create_v1_mock_binary_sensor_entity_entry(
        hass, v1_mock_config_entry.entry_id, device_entry_id
    )

    # Trigger migration.
    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(v1_mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test migrated config entry.
    assert v1_mock_config_entry.unique_id is None
    assert v1_mock_config_entry.data == {
        CONF_NAME: DEFAULT_NAME,
        CONF_ADDRESS: TEST_HOST,
    }
    assert v1_mock_config_entry.version == 3
    assert v1_mock_config_entry.state is ConfigEntryState.LOADED


async def test_entry_migration_v3_failure(
    hass: HomeAssistant, v1_mock_config_entry: MockConfigEntry
) -> None:
    """Test failed entry migration from version 2 to 3."""
    v1_mock_config_entry.add_to_hass(hass)

    device_entry_id = create_v1_mock_device_entry(hass, v1_mock_config_entry.entry_id)
    create_v1_mock_sensor_entity_entries(
        hass, v1_mock_config_entry.entry_id, device_entry_id
    )
    create_v1_mock_binary_sensor_entity_entry(
        hass, v1_mock_config_entry.entry_id, device_entry_id
    )

    # Trigger migration.
    with patch(
        "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
        side_effect=[
            ValueError,  # async_migrate_entry
            ValueError,  # async_migrate_entry
        ],
    ):
        assert not await hass.config_entries.async_setup(v1_mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test config entry.
    assert v1_mock_config_entry.version == 2
    assert v1_mock_config_entry.state is ConfigEntryState.MIGRATION_ERROR
