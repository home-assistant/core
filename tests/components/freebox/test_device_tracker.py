"""Tests for the Freebox device trackers."""

from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.components.freebox.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import setup_platform
from .const import (
    DATA_LAN_GET_HOSTS_LIST,
    DATA_LAN_GET_HOSTS_LIST_GUEST,
    DATA_SYSTEM_GET_CONFIG,
)

from tests.common import async_fire_time_changed


async def test_router_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    router: Mock,
) -> None:
    """Test get_hosts_list invoqued multiple times if freebox into router mode."""
    await setup_platform(hass, DEVICE_TRACKER_DOMAIN)

    assert router().lan.get_hosts_list.call_count == 2

    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert router().lan.get_hosts_list.call_count == 4


async def test_bridge_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    router_bridge_mode: Mock,
) -> None:
    """Test get_interfaces invoqued once if freebox into bridge mode."""
    await setup_platform(hass, DEVICE_TRACKER_DOMAIN)

    assert router_bridge_mode().lan.get_interfaces.call_count == 1

    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # If get_interfaces failed, not called again
    assert router_bridge_mode().lan.get_interfaces.call_count == 1


async def test_remove_stale_tracker_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    router: Mock,
) -> None:
    """Stale tracker entities are pruned when the Freebox forgets a MAC."""
    await setup_platform(hass, DEVICE_TRACKER_DOMAIN)

    stale_unique_id = dr.format_mac(DATA_LAN_GET_HOSTS_LIST[1]["l2ident"]["id"])
    assert (
        entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, stale_unique_id
        )
        is not None
    )

    # Freebox no longer returns this MAC after the user "Oublier"s the device.
    remaining_hosts = [
        host
        for host in DATA_LAN_GET_HOSTS_LIST
        if dr.format_mac(host["l2ident"]["id"]) != stale_unique_id
    ]
    router().lan.get_hosts_list = AsyncMock(
        side_effect=lambda interface: (
            remaining_hosts if interface == "pub" else DATA_LAN_GET_HOSTS_LIST_GUEST
        )
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, stale_unique_id
        )
        is None
    )

    # Active and router entries are untouched.
    assert (
        entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN,
            DOMAIN,
            dr.format_mac(DATA_LAN_GET_HOSTS_LIST[0]["l2ident"]["id"]),
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, dr.format_mac(DATA_SYSTEM_GET_CONFIG["mac"])
        )
        is not None
    )
