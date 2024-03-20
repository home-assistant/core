"""Tests for Tradfri setup."""

from unittest.mock import MagicMock

from homeassistant.components import tradfri
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import GATEWAY_ID

from tests.common import MockConfigEntry


async def test_entry_setup_unload(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_api_factory: MagicMock
) -> None:
    """Test config entry setup and unload."""
    config_entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host",
            tradfri.CONF_IDENTITY: "mock-identity",
            tradfri.CONF_KEY: "mock-key",
            tradfri.CONF_GATEWAY_ID: GATEWAY_ID,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert device_entries
    device_entry = device_entries[0]
    assert device_entry.identifiers == {
        (tradfri.DOMAIN, config_entry.data[tradfri.CONF_GATEWAY_ID])
    }
    assert device_entry.manufacturer == "IKEA of Sweden"
    assert device_entry.name == "Gateway"
    assert device_entry.model == "E1526"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_api_factory.shutdown.call_count == 1


async def test_remove_stale_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test remove stale device registry entries."""
    config_entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host",
            tradfri.CONF_IDENTITY: "mock-identity",
            tradfri.CONF_KEY: "mock-key",
            tradfri.CONF_GATEWAY_ID: GATEWAY_ID,
        },
    )

    config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(tradfri.DOMAIN, "stale_device_id")},
    )
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 1
    device_entry = device_entries[0]
    assert device_entry.identifiers == {(tradfri.DOMAIN, "stale_device_id")}

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    # Check that only the gateway device entry remains.
    assert len(device_entries) == 1
    device_entry = device_entries[0]
    assert device_entry.identifiers == {
        (tradfri.DOMAIN, config_entry.data[tradfri.CONF_GATEWAY_ID])
    }
    assert device_entry.manufacturer == "IKEA of Sweden"
    assert device_entry.name == "Gateway"
    assert device_entry.model == "E1526"
