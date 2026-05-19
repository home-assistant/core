"""Tests for the Freebox init."""

from unittest.mock import ANY, AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
from pytest_unordered import unordered

from homeassistant.components.device_tracker import DOMAIN as DT_DOMAIN
from homeassistant.components.freebox import (
    SCAN_INTERVAL,
    async_remove_config_entry_device,
)
from homeassistant.components.freebox.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .const import (
    DATA_HOME_GET_NODES,
    DATA_LAN_GET_HOSTS_LIST,
    DATA_SYSTEM_GET_CONFIG,
    MOCK_HOST,
    MOCK_PORT,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup(hass: HomeAssistant, router: Mock) -> None:
    """Test setup of integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries() == unordered([entry, ANY])

    assert router.call_count == 1
    assert router().open.call_count == 1


async def test_setup_import(hass: HomeAssistant, router: Mock) -> None:
    """Test setup of integration from import."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT}}
    )
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries() == unordered([entry, ANY])

    assert router.call_count == 1
    assert router().open.call_count == 1


async def test_unload_remove(hass: HomeAssistant, router: Mock) -> None:
    """Test unload and remove of integration."""
    entity_id_dt = f"{DT_DOMAIN}.freebox_server_r2"
    entity_id_sensor = f"{SENSOR_DOMAIN}.freebox_server_r2_freebox_download_speed"
    entity_id_switch = f"{SWITCH_DOMAIN}.freebox_server_r2_freebox_wifi"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state_dt = hass.states.get(entity_id_dt)
    assert state_dt
    state_sensor = hass.states.get(entity_id_sensor)
    assert state_sensor
    state_switch = hass.states.get(entity_id_switch)
    assert state_switch

    await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    state_dt = hass.states.get(entity_id_dt)
    assert state_dt.state == STATE_UNAVAILABLE
    state_sensor = hass.states.get(entity_id_sensor)
    assert state_sensor.state == STATE_UNAVAILABLE
    state_switch = hass.states.get(entity_id_switch)
    assert state_switch.state == STATE_UNAVAILABLE

    assert router().close.call_count == 1

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert router().close.call_count == 1
    assert entry.state is ConfigEntryState.NOT_LOADED
    state_dt = hass.states.get(entity_id_dt)
    assert state_dt is None
    state_sensor = hass.states.get(entity_id_sensor)
    assert state_sensor is None
    state_switch = hass.states.get(entity_id_switch)
    assert state_switch is None


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    router: Mock,
) -> None:
    """Test removal rules for Freebox devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    router_mac = dr.format_mac(DATA_SYSTEM_GET_CONFIG["mac"])

    # The Freebox router itself cannot be removed.
    router_device = device_registry.async_get_device(identifiers={(DOMAIN, router_mac)})
    assert router_device is not None
    assert await async_remove_config_entry_device(hass, entry, router_device) is False

    # A Home device still reported by the Freebox cannot be removed
    # (node id 7 is the alarm system in the test fixture).
    home_device = device_registry.async_get_device(identifiers={(DOMAIN, 7)})
    assert home_device is not None
    assert await async_remove_config_entry_device(hass, entry, home_device) is False

    # A tracked LAN device whose MAC is still on the Freebox cannot be removed.
    tracked_device = device_registry.async_get_device(
        connections={
            (
                dr.CONNECTION_NETWORK_MAC,
                dr.format_mac(DATA_LAN_GET_HOSTS_LIST[0]["l2ident"]["id"]),
            )
        }
    )
    assert tracked_device is not None
    assert await async_remove_config_entry_device(hass, entry, tracked_device) is False

    # A Home device that the Freebox no longer reports can be removed.
    stale_home_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "999")},
    )
    assert (
        await async_remove_config_entry_device(hass, entry, stale_home_device) is True
    )

    # A LAN device whose MAC is gone from the Freebox can be removed.
    stale_tracked_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac("AA:BB:CC:DD:EE:FF"))},
    )
    assert (
        await async_remove_config_entry_device(hass, entry, stale_tracked_device)
        is True
    )
