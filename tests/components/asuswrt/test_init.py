"""Tests for the AsusWrt integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import sensor
from homeassistant.components.asuswrt.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

from .common import CONFIG_DATA_HTTP, CONFIG_DATA_TELNET, HOST, ROUTER_MAC_ADDR

from tests.common import MockConfigEntry


async def test_disconnect_on_stop(hass: HomeAssistant, connect_legacy) -> None:
    """Test we close the connection with the router when Home Assistants stops."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
        unique_id=ROUTER_MAC_ADDR,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert connect_legacy.return_value.async_disconnect.await_count == 1
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("connect_http", "connect_http_sens_detect")
async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the router device registry entry, including the network MAC connection."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_HTTP,
        unique_id=ROUTER_MAC_ADDR,
    )
    config_entry.add_to_hass(hass)

    # Router sensors are disabled by default; pre-enable one so the router
    # device is registered in the device registry.
    unique_id_prefix = slugify(ROUTER_MAC_ADDR)
    sensor_id = slugify("sensor_rx_bytes")
    entity_registry.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        f"{unique_id_prefix}_{sensor_id}",
        suggested_object_id=f"{slugify(HOST)}_{sensor_id}",
        config_entry=config_entry,
        disabled_by=None,
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, ROUTER_MAC_ADDR)}
    )
    assert device_entry == snapshot
