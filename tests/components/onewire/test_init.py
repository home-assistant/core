"""Tests for 1-Wire config flow."""
from homeassistant import config_entries
from homeassistant.components import onewire
from homeassistant.components.onewire.const import CONF_TYPE_SYSBUS

from tests.common import MockConfigEntry


async def setup_onewire_integration(hass):
    """Create the 1-Wire integration."""
    config_entry = MockConfigEntry(
        domain=onewire.DOMAIN,
        source="user",
        data={
            onewire.config_flow.CONF_TYPE: CONF_TYPE_SYSBUS,
        },
        connection_class=config_entries.CONN_CLASS_LOCAL_POLL,
        options={},
        entry_id="1",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    config_entry = await setup_onewire_integration(hass)

    assert await onewire.async_unload_entry(hass, config_entry)
