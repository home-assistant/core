"""Tests for the Bravia TV integration."""

from unittest.mock import AsyncMock

from homeassistant.components.braviatv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_migrate_entry_from_cid_to_mac(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_bravia_client: AsyncMock,
) -> None:
    """Test migration from cid based unique_id to mac based unique_id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="very_unique_string",
        data={
            CONF_HOST: "bravia-host",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PIN: "1234",
        },
        version=1,
        title="TV-Model",
    )
    config_entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        "very_unique_string",
        config_entry=config_entry,
    )
    entity_terminate = entity_registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        "very_unique_string_terminate_apps",
        config_entry=config_entry,
    )
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "very_unique_string")},
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.unique_id == "aa:bb:cc:dd:ee:ff"
    assert config_entry.version == 2

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity.unique_id == "aa:bb:cc:dd:ee:ff"
    migrated_terminate = entity_registry.async_get(entity_terminate.entity_id)
    assert migrated_terminate.unique_id == "aa:bb:cc:dd:ee:ff_terminate_apps"

    assert not device_registry.async_get_devices(
        identifiers={(DOMAIN, "very_unique_string")}
    )
    assert device_registry.async_get(device.id).identifiers == {
        (DOMAIN, "aa:bb:cc:dd:ee:ff")
    }


async def test_migrate_entry_with_empty_cid_to_mac(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_bravia_client: AsyncMock,
) -> None:
    """Test migration from empty unique_id to mac based unique_id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="",
        data={
            CONF_HOST: "bravia-host",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PIN: "1234",
        },
        version=1,
        title="TV-Model",
    )
    config_entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        "",
        config_entry=config_entry,
    )
    entity_terminate = entity_registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        "_terminate_apps",
        config_entry=config_entry,
    )
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "")},
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.unique_id == "aa:bb:cc:dd:ee:ff"
    assert config_entry.version == 2

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity.unique_id == "aa:bb:cc:dd:ee:ff"
    migrated_terminate = entity_registry.async_get(entity_terminate.entity_id)
    assert migrated_terminate.unique_id == "aa:bb:cc:dd:ee:ff_terminate_apps"

    assert not device_registry.async_get_devices(identifiers={(DOMAIN, "")})
    assert device_registry.async_get(device.id).identifiers == {
        (DOMAIN, "aa:bb:cc:dd:ee:ff")
    }
