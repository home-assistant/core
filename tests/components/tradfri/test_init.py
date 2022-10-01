"""Tests for Tradfri setup."""
from unittest.mock import patch

from homeassistant.components import tradfri
from homeassistant.helpers import device_registry as dr

from . import GATEWAY_ID

from tests.common import MockConfigEntry


async def test_entry_setup_unload(hass, mock_api_factory):
    """Test config entry setup and unload."""
    entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host",
            tradfri.CONF_IDENTITY: "mock-identity",
            tradfri.CONF_KEY: "mock-key",
            tradfri.CONF_GATEWAY_ID: GATEWAY_ID,
        },
    )

    entry.add_to_hass(hass)
    with patch.object(
        hass.config_entries, "async_forward_entry_setup", return_value=True
    ) as setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert setup.call_count == len(tradfri.PLATFORMS)

    dev_reg = dr.async_get(hass)
    dev_entries = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)

    assert dev_entries
    dev_entry = dev_entries[0]
    assert dev_entry.identifiers == {
        (tradfri.DOMAIN, entry.data[tradfri.CONF_GATEWAY_ID])
    }
    assert dev_entry.manufacturer == "IKEA of Sweden"
    assert dev_entry.name == "Gateway"
    assert dev_entry.model == "E1526"

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as unload:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert unload.call_count == len(tradfri.PLATFORMS)
        assert mock_api_factory.shutdown.call_count == 1


async def test_remove_stale_devices(hass, mock_api_factory):
    """Test remove stale device registry entries."""
    entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host",
            tradfri.CONF_IDENTITY: "mock-identity",
            tradfri.CONF_KEY: "mock-key",
            tradfri.CONF_GATEWAY_ID: GATEWAY_ID,
        },
    )

    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(tradfri.DOMAIN, "stale_device_id")},
    )
    dev_entries = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)

    assert len(dev_entries) == 1
    dev_entry = dev_entries[0]
    assert dev_entry.identifiers == {(tradfri.DOMAIN, "stale_device_id")}

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    dev_entries = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)

    # Check that only the gateway device entry remains.
    assert len(dev_entries) == 1
    dev_entry = dev_entries[0]
    assert dev_entry.identifiers == {
        (tradfri.DOMAIN, entry.data[tradfri.CONF_GATEWAY_ID])
    }
    assert dev_entry.manufacturer == "IKEA of Sweden"
    assert dev_entry.name == "Gateway"
    assert dev_entry.model == "E1526"
