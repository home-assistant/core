"""Tests for Tradfri setup."""
from unittest.mock import patch

from homeassistant.components import tradfri
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_entry_setup_unload(hass, api_factory, gateway_id):
    """Test config entry setup and unload."""
    entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host",
            tradfri.CONF_IDENTITY: "mock-identity",
            tradfri.CONF_KEY: "mock-key",
            tradfri.CONF_IMPORT_GROUPS: True,
            tradfri.CONF_GATEWAY_ID: gateway_id,
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
    assert dev_entry.manufacturer == tradfri.ATTR_TRADFRI_MANUFACTURER
    assert dev_entry.name == tradfri.ATTR_TRADFRI_GATEWAY
    assert dev_entry.model == tradfri.ATTR_TRADFRI_GATEWAY_MODEL

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as unload:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert unload.call_count == len(tradfri.PLATFORMS)
        assert api_factory.shutdown.call_count == 1
