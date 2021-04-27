"""Tests for 1-Wire config flow."""
from unittest.mock import patch

from pyownet.protocol import ConnError, OwnetError

from homeassistant.components.onewire.const import CONF_TYPE_OWSERVER, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
    SOURCE_USER,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    setup_onewire_owserver_integration,
    setup_onewire_patched_owserver_integration,
    setup_onewire_sysbus_integration,
    setup_owproxy_mock_devices,
)

from tests.common import MockConfigEntry, mock_device_registry, mock_registry


async def test_owserver_connect_failure(hass):
    """Test connection failure raises ConfigEntryNotReady."""
    config_entry_owserver = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
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
        source=SOURCE_USER,
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


@patch("homeassistant.components.onewire.onewirehub.protocol.proxy")
async def test_registry_cleanup(owproxy, hass):
    """Test for 1-Wire device.

    As they would be on a clean setup: all binary-sensors and switches disabled.
    """
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    # Initialise with two components
    setup_owproxy_mock_devices(
        owproxy, SENSOR_DOMAIN, ["10.111111111111", "28.111111111111"]
    )
    with patch("homeassistant.components.onewire.PLATFORMS", [SENSOR_DOMAIN]):
        await setup_onewire_patched_owserver_integration(hass)
        await hass.async_block_till_done()

    assert len(dr.async_entries_for_config_entry(device_registry, "2")) == 2
    assert len(er.async_entries_for_config_entry(entity_registry, "2")) == 2

    # Second item has disappeared from bus, and was removed manually from the front-end
    setup_owproxy_mock_devices(owproxy, SENSOR_DOMAIN, ["10.111111111111"])
    entity_registry.async_remove("sensor.28_111111111111_temperature")
    await hass.async_block_till_done()

    assert len(er.async_entries_for_config_entry(entity_registry, "2")) == 1
    assert len(dr.async_entries_for_config_entry(device_registry, "2")) == 2

    # Second item has disappeared from bus, and was removed manually from the front-end
    with patch("homeassistant.components.onewire.PLATFORMS", [SENSOR_DOMAIN]):
        await hass.config_entries.async_reload("2")
        await hass.async_block_till_done()

    assert len(er.async_entries_for_config_entry(entity_registry, "2")) == 1
    assert len(dr.async_entries_for_config_entry(device_registry, "2")) == 1
