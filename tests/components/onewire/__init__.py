"""Tests for 1-Wire integration."""

from unittest.mock import patch

from homeassistant.components.onewire.const import (
    CONF_MOUNT_DIR,
    CONF_NAMES,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
)
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE

from tests.common import MockConfigEntry


async def setup_onewire_sysbus_integration(hass):
    """Create the 1-Wire integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source="user",
        data={
            CONF_TYPE: CONF_TYPE_SYSBUS,
            CONF_MOUNT_DIR: DEFAULT_SYSBUS_MOUNT_DIR,
        },
        unique_id=f"{CONF_TYPE_SYSBUS}:{DEFAULT_SYSBUS_MOUNT_DIR}",
        connection_class=CONN_CLASS_LOCAL_POLL,
        options={},
        entry_id="1",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.onewire.onewirehub.os.path.isdir", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def setup_onewire_owserver_integration(hass):
    """Create the 1-Wire integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source="user",
        data={
            CONF_TYPE: CONF_TYPE_OWSERVER,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1234,
        },
        connection_class=CONN_CLASS_LOCAL_POLL,
        options={},
        entry_id="2",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        return config_entry


async def setup_onewire_patched_owserver_integration(hass):
    """Create the 1-Wire integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source="user",
        data={
            CONF_TYPE: CONF_TYPE_OWSERVER,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1234,
            CONF_NAMES: {
                "10.111111111111": "My DS18B20",
            },
        },
        connection_class=CONN_CLASS_LOCAL_POLL,
        options={},
        entry_id="2",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
