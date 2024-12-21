"""Tests of the initialization of the twinkly integration."""

from unittest.mock import patch
from uuid import uuid4

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.twinkly.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import TEST_HOST, TEST_MAC, TEST_MODEL, TEST_NAME_ORIGINAL, ClientMock

from tests.common import MockConfigEntry


async def test_load_unload_entry(hass: HomeAssistant) -> None:
    """Validate that setup entry also configure the client."""
    client = ClientMock()

    device_id = str(uuid4())
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_ID: device_id,
            CONF_NAME: TEST_NAME_ORIGINAL,
            CONF_MODEL: TEST_MODEL,
        },
        entry_id=device_id,
        unique_id=TEST_MAC,
        minor_version=2,
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.twinkly.Twinkly", return_value=client):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Validate that config entry is retried."""
    client = ClientMock()
    client.is_offline = True

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_ID: id,
            CONF_NAME: TEST_NAME_ORIGINAL,
            CONF_MODEL: TEST_MODEL,
        },
        minor_version=2,
        unique_id=TEST_MAC,
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.twinkly.Twinkly", return_value=client):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mac_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Validate that the unique_id is migrated to the MAC address."""
    client = ClientMock()

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=1,
        unique_id="unique_id",
        data={
            CONF_HOST: TEST_HOST,
            CONF_ID: id,
            CONF_NAME: TEST_NAME_ORIGINAL,
            CONF_MODEL: TEST_MODEL,
        },
    )
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        LIGHT_DOMAIN,
        DOMAIN,
        config_entry.unique_id,
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.unique_id)},
    )

    with patch("homeassistant.components.twinkly.Twinkly", return_value=client):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED

    assert entity_registry.async_get(entity_entry.entity_id).unique_id == TEST_MAC
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, config_entry.unique_id)}
    ).identifiers == {(DOMAIN, TEST_MAC)}
    assert config_entry.unique_id == TEST_MAC
