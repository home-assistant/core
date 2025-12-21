"""Test Hue migration logic."""

from unittest.mock import Mock, patch

from homeassistant.components import hue
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.json import JsonArrayType

from tests.common import MockConfigEntry


async def test_migrate_api_key(hass: HomeAssistant) -> None:
    """Test if username gets migrated to api_key."""
    config_entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 2, "username": "abcdefgh"},
    )
    config_entry.add_to_hass(hass)
    await hue.migration.check_migration(hass, config_entry)
    # the username property should have been migrated to api_key
    assert config_entry.data == {
        "host": "0.0.0.0",
        "api_version": 2,
        "api_key": "abcdefgh",
    }


async def test_auto_switchover(hass: HomeAssistant) -> None:
    """Test if config entry from v1 automatically switches to v2."""
    config_entry = MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "0.0.0.0", "api_version": 1, "username": "abcdefgh"},
    )
    config_entry.add_to_hass(hass)

    with (
        patch.object(hue.migration, "is_v2_bridge", retun_value=True),
        patch.object(hue.migration, "handle_v2_migration") as mock_mig,
    ):
        await hue.migration.check_migration(hass, config_entry)
        assert len(mock_mig.mock_calls) == 1
        # the api version should now be version 2
        assert config_entry.data == {
            "host": "0.0.0.0",
            "api_version": 2,
            "api_key": "abcdefgh",
        }


async def test_light_entity_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_bridge_v2: Mock,
    mock_config_entry_v2: MockConfigEntry,
    v2_resources_test_data: JsonArrayType,
) -> None:
    """Test if entity schema for lights migrates from v1 to v2."""
    config_entry = mock_bridge_v2.config_entry = mock_config_entry_v2
    config_entry.add_to_hass(hass)

    # create device/entity with V1 schema in registry
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(hue.DOMAIN, "00:17:88:01:09:aa:bb:65-0b")},
    )
    entity_registry.async_get_or_create(
        "light",
        hue.DOMAIN,
        "00:17:88:01:09:aa:bb:65-0b",
        suggested_object_id="migrated_light_1",
        device_id=device.id,
    )

    # now run the migration and check results
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.hue.migration.HueBridgeV2",
        return_value=mock_bridge_v2.api,
    ):
        await hue.migration.handle_v2_migration(hass, config_entry)

    # migrated device should now have the new identifier (guid) instead of old style (mac)
    migrated_device = device_registry.async_get(device.id)
    assert migrated_device is not None
    assert migrated_device.identifiers == {
        (hue.DOMAIN, "0b216218-d811-4c95-8c55-bbcda50f9d50")
    }
    # the entity should have the new unique_id (guid)
    migrated_entity = entity_registry.async_get("light.migrated_light_1")
    assert migrated_entity is not None
    assert migrated_entity.unique_id == "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1"


async def test_sensor_entity_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_bridge_v2: Mock,
    mock_config_entry_v2: MockConfigEntry,
    v2_resources_test_data: JsonArrayType,
) -> None:
    """Test if entity schema for sensors migrates from v1 to v2."""
    config_entry = mock_bridge_v2.config_entry = mock_config_entry_v2
    config_entry.add_to_hass(hass)

    # create device with V1 schema in registry for Hue motion sensor
    device_mac = "00:17:aa:bb:cc:09:ac:c3"
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(hue.DOMAIN, device_mac)}
    )

    # mapping of device_class to new id
    sensor_mappings = {
        ("temperature", "sensor", "66466e14-d2fa-4b96-b2a0-e10de9cd8b8b"),
        ("illuminance", "sensor", "d504e7a4-9a18-4854-90fd-c5b6ac102c40"),
        ("battery", "sensor", "669f609d-4860-4f1c-bc25-7a9cec1c3b6c"),
        ("motion", "binary_sensor", "b6896534-016d-4052-8cb4-ef04454df62c"),
    }

    # create entities with V1 schema in registry for Hue motion sensor
    for dev_class, platform, _ in sensor_mappings:
        entity_registry.async_get_or_create(
            platform,
            hue.DOMAIN,
            f"{device_mac}-{dev_class}",
            suggested_object_id=f"hue_migrated_{dev_class}_sensor",
            device_id=device.id,
            original_device_class=dev_class,
        )

    # now run the migration and check results
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.hue.migration.HueBridgeV2",
        return_value=mock_bridge_v2.api,
    ):
        await hue.migration.handle_v2_migration(hass, config_entry)

    # migrated device should now have the new identifier (guid) instead of old style (mac)
    migrated_device = device_registry.async_get(device.id)
    assert migrated_device is not None
    assert migrated_device.identifiers == {
        (hue.DOMAIN, "2330b45d-6079-4c6e-bba6-1b68afb1a0d6")
    }
    # the entities should have the correct V2 unique_id (guid)
    for dev_class, platform, new_id in sensor_mappings:
        migrated_entity = entity_registry.async_get(
            f"{platform}.hue_migrated_{dev_class}_sensor"
        )
        assert migrated_entity is not None
        assert migrated_entity.unique_id == new_id


async def test_group_entity_migration_with_v1_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_bridge_v2: Mock,
    mock_config_entry_v2: MockConfigEntry,
    v2_resources_test_data: JsonArrayType,
) -> None:
    """Test if entity schema for grouped_lights migrates from v1 to v2."""
    config_entry = mock_bridge_v2.config_entry = mock_config_entry_v2
    config_entry.add_to_hass(hass)

    # create (deviceless) entity with V1 schema in registry
    # using the legacy style group id as unique id
    entity_registry.async_get_or_create(
        "light",
        hue.DOMAIN,
        "3",
        suggested_object_id="hue_migrated_grouped_light",
        config_entry=config_entry,
    )

    # now run the migration and check results
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.hue.migration.HueBridgeV2",
        return_value=mock_bridge_v2.api,
    ):
        await hue.migration.handle_v2_migration(hass, config_entry)

    # the entity should have the new identifier (guid)
    migrated_entity = entity_registry.async_get("light.hue_migrated_grouped_light")
    assert migrated_entity is not None
    assert migrated_entity.unique_id == "e937f8db-2f0e-49a0-936e-027e60e15b34"


async def test_group_entity_migration_with_v2_group_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_bridge_v2: Mock,
    mock_config_entry_v2: MockConfigEntry,
    v2_resources_test_data: JsonArrayType,
) -> None:
    """Test if entity schema for grouped_lights migrates from v1 to v2."""
    config_entry = mock_bridge_v2.config_entry = mock_config_entry_v2
    config_entry.add_to_hass(hass)

    # create (deviceless) entity with V1 schema in registry
    # using the V2 group id as unique id
    entity_registry.async_get_or_create(
        "light",
        hue.DOMAIN,
        "6ddc9066-7e7d-4a03-a773-c73937968296",
        suggested_object_id="hue_migrated_grouped_light",
        config_entry=config_entry,
    )

    # now run the migration and check results
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.hue.migration.HueBridgeV2",
        return_value=mock_bridge_v2.api,
    ):
        await hue.migration.handle_v2_migration(hass, config_entry)

    # the entity should have the new identifier (guid)
    migrated_entity = entity_registry.async_get("light.hue_migrated_grouped_light")
    assert migrated_entity is not None
    assert migrated_entity.unique_id == "e937f8db-2f0e-49a0-936e-027e60e15b34"
