"""Tests for the Steamist integration."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from aiosteamist import Steamist, SteamistStatus
from discovery30303 import AIODiscovery30303, Device30303

from homeassistant.components import steamist
from homeassistant.components.steamist.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_ASYNC_GET_STATUS_INACTIVE = SteamistStatus(
    temp=70, temp_units="F", minutes_remain=0, active=False
)
MOCK_ASYNC_GET_STATUS_ACTIVE = SteamistStatus(
    temp=102, temp_units="F", minutes_remain=14, active=True
)
DEVICE_IP_ADDRESS = "127.0.0.1"
DEVICE_NAME = "Master Bath"
DEVICE_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
DEVICE_HOSTNAME = "MY450-EEFF"
FORMATTED_MAC_ADDRESS = dr.format_mac(DEVICE_MAC_ADDRESS)
DEVICE_MODEL = "MY450"
DEVICE_30303 = Device30303(
    ipaddress=DEVICE_IP_ADDRESS,
    name=DEVICE_NAME,
    mac=DEVICE_MAC_ADDRESS,
    hostname=DEVICE_HOSTNAME,
)
DEVICE_30303_NOT_STEAMIST = Device30303(
    ipaddress=DEVICE_IP_ADDRESS,
    name=DEVICE_NAME,
    mac=DEVICE_MAC_ADDRESS,
    hostname="not_steamist",
)
DISCOVERY_30303 = {
    "ipaddress": DEVICE_IP_ADDRESS,
    "name": DEVICE_NAME,
    "mac": DEVICE_MAC_ADDRESS,
    "hostname": DEVICE_HOSTNAME,
}
DISCOVERY_30303_NOT_STEAMIST = {
    "ipaddress": DEVICE_IP_ADDRESS,
    "name": DEVICE_NAME,
    "mac": DEVICE_MAC_ADDRESS,
    "hostname": "not_steamist",
}
DEFAULT_ENTRY_DATA = {
    CONF_HOST: DEVICE_IP_ADDRESS,
    CONF_NAME: DEVICE_NAME,
    CONF_MODEL: DEVICE_MODEL,
}


async def _async_setup_entry_with_status(
    hass: HomeAssistant, status: SteamistStatus
) -> tuple[Steamist, ConfigEntry]:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    config_entry.add_to_hass(hass)
    client = _mocked_steamist()
    client.async_get_status = AsyncMock(return_value=status)
    with _patch_status(status, client):
        await async_setup_component(hass, steamist.DOMAIN, {steamist.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    return client, config_entry


def _mocked_steamist() -> Steamist:
    client = MagicMock(auto_spec=Steamist)
    client.async_turn_on_steam = AsyncMock()
    client.async_turn_off_steam = AsyncMock()
    client.async_get_status = AsyncMock(return_value=MOCK_ASYNC_GET_STATUS_ACTIVE)
    return client


def _patch_status(status: SteamistStatus, client: Steamist | None = None):
    if client is None:
        client = _mocked_steamist()
        client.async_get_status = AsyncMock(return_value=status)

    @contextmanager
    def _patcher():
        with patch("homeassistant.components.steamist.Steamist", return_value=client):
            yield

    return _patcher()


def _patch_discovery(device=None, no_device=False):
    mock_aio_discovery = MagicMock(auto_spec=AIODiscovery30303)
    if no_device:
        mock_aio_discovery.async_scan = AsyncMock(side_effect=OSError)
    else:
        mock_aio_discovery.async_scan = AsyncMock()
    mock_aio_discovery.found_devices = [] if no_device else [device or DEVICE_30303]

    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.steamist.discovery.AIODiscovery30303",
            return_value=mock_aio_discovery,
        ):
            yield

    return _patcher()
