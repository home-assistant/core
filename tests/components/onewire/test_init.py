"""Tests for 1-Wire config flow."""
from pyownet.protocol import ConnError, OwnetError

from homeassistant.components.onewire.const import CONF_TYPE_OWSERVER, DOMAIN
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE

from . import setup_onewire_owserver_integration, setup_onewire_sysbus_integration

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_owserver_connect_failure(hass):
    """Test connection failure raises ConfigEntryNotReady."""
    config_entry_owserver = MockConfigEntry(
        domain=DOMAIN,
        source="user",
        data={
            CONF_TYPE: CONF_TYPE_OWSERVER,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: "1234",
        },
        unique_id=f"{CONF_TYPE_OWSERVER}:1.2.3.4:1234",
        connection_class=CONN_CLASS_LOCAL_POLL,
        options={},
        entry_id="2",
    )
    config_entry_owserver.add_to_hass(hass)

    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
        side_effect=ConnError,
    ):
        await hass.config_entries.async_setup(config_entry_owserver.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry_owserver.state == ENTRY_STATE_SETUP_RETRY
    assert not hass.data.get(DOMAIN)


async def test_failed_owserver_listing(hass):
    """Create the 1-Wire integration."""
    config_entry_owserver = MockConfigEntry(
        domain=DOMAIN,
        source="user",
        data={
            CONF_TYPE: CONF_TYPE_OWSERVER,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: "1234",
        },
        unique_id=f"{CONF_TYPE_OWSERVER}:1.2.3.4:1234",
        connection_class=CONN_CLASS_LOCAL_POLL,
        options={},
        entry_id="2",
    )
    config_entry_owserver.add_to_hass(hass)

    with patch("homeassistant.components.onewire.onewirehub.protocol.proxy") as owproxy:
        owproxy.return_value.dir.side_effect = OwnetError
        await hass.config_entries.async_setup(config_entry_owserver.entry_id)
        await hass.async_block_till_done()

        return config_entry_owserver


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    config_entry_owserver = await setup_onewire_owserver_integration(hass)
    config_entry_sysbus = await setup_onewire_sysbus_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert config_entry_owserver.state == ENTRY_STATE_LOADED
    assert config_entry_sysbus.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(config_entry_owserver.entry_id)
    assert await hass.config_entries.async_unload(config_entry_sysbus.entry_id)
    await hass.async_block_till_done()

    assert config_entry_owserver.state == ENTRY_STATE_NOT_LOADED
    assert config_entry_sysbus.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
