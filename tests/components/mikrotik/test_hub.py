"""Test Mikrotik hub."""
from unittest.mock import patch

import librouteros
import pytest

from homeassistant import config_entries
from homeassistant.components import mikrotik
from homeassistant.components.mikrotik.const import (
    CLIENTS,
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_DHCP_SERVER_TRACK_MODE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from . import (
    ARP_DATA,
    DEVICE_1_DHCP,
    DEVICE_1_WIRELESS,
    DEVICE_2_DHCP,
    DEVICE_2_WIRELESS,
    DHCP_DATA,
    MOCK_DATA,
    MOCK_OPTIONS,
    PING_FAIL,
    PING_SUCCESS,
    WIRELESS_DATA,
)

from tests.common import MockConfigEntry


async def setup_mikrotik_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    support_capsman: bool = True,
    support_wireless: bool = True,
    dhcp_data: list = DHCP_DATA,
    wireless_data: list = WIRELESS_DATA,
    arp_data: list = ARP_DATA,
    ping_result: list = PING_SUCCESS,
) -> mikrotik.MikrotikHub:
    """Set up Mikrotik integration successfully."""

    def mock_command(self, cmd, params=None):
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_CAPSMAN]:
            return support_capsman
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIRELESS]:
            return support_wireless
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP]:
            return dhcp_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.CAPSMAN]:
            return wireless_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.WIRELESS]:
            return wireless_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.ARP]:
            return arp_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IDENTITY]:
            return [{"name": "router"}]
        if cmd == mikrotik.const.CMD_PING:
            return ping_result
        return {}

    with patch.object(mikrotik.hub.MikrotikHubData, "command", new=mock_command):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return hass.data[mikrotik.DOMAIN][config_entry.entry_id]


async def test_hub_support_capsman(hass: HomeAssistant) -> None:
    """Test clients from capsman interface added when supported."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(
        hass,
        entry,
        support_capsman=True,
        support_wireless=False,
        wireless_data=[DEVICE_1_WIRELESS],
        dhcp_data=[DEVICE_1_DHCP, DEVICE_2_DHCP],
    )

    assert DEVICE_1_WIRELESS["mac-address"] in hub.data
    assert DEVICE_1_WIRELESS["mac-address"] in hass.data[DOMAIN][CLIENTS]
    assert DEVICE_2_DHCP["mac-address"] not in hub.data


async def test_hub_support_wireless(hass: HomeAssistant) -> None:
    """Test clients from capsman interface added when supported."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(
        hass,
        entry,
        support_capsman=False,
        support_wireless=True,
        wireless_data=[DEVICE_1_WIRELESS],
        dhcp_data=[DEVICE_1_DHCP, DEVICE_2_DHCP],
    )

    assert DEVICE_1_WIRELESS["mac-address"] in hub.data
    assert DEVICE_1_WIRELESS["mac-address"] in hass.data[DOMAIN][CLIENTS]
    assert DEVICE_2_DHCP["mac-address"] not in hub.data


async def test_hub_not_support_wireless(hass):
    """Test clients added from dhcp_server when hub doesn't support wireless interfaces."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(
        hass,
        entry,
        support_capsman=False,
        support_wireless=False,
        wireless_data=[],
        dhcp_data=[DEVICE_1_DHCP, DEVICE_2_DHCP],
    )

    assert hub.hub_data.use_dhcp_server
    assert "00:00:00:00:00:01" in hub.data
    assert "00:00:00:00:00:01" in hass.data[DOMAIN][CLIENTS]
    assert "00:00:00:00:00:02" in hub.data
    assert "00:00:00:00:00:02" in hass.data[DOMAIN][CLIENTS]


async def test_hub_does_not_add_clients_from_other_entires(
    hass: HomeAssistant,
) -> None:
    """Hub should not add clients initially registered by other hub entries."""

    # setup hub 1
    entry_1 = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS
    )
    entry_1.add_to_hass(hass)
    hub1 = await setup_mikrotik_entry(
        hass,
        entry_1,
        wireless_data=[DEVICE_1_WIRELESS],
        dhcp_data=[DEVICE_1_DHCP, DEVICE_2_DHCP],
    )

    assert DEVICE_1_WIRELESS["mac-address"] in hub1.data
    assert DEVICE_1_WIRELESS["mac-address"] in hass.data[DOMAIN][CLIENTS]

    # setup hub 2
    hub2_data = {
        CONF_HOST: "0.0.0.2",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_PORT: 8278,
        CONF_VERIFY_SSL: False,
    }
    entry_2 = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=hub2_data, options=MOCK_OPTIONS
    )
    entry_2.add_to_hass(hass)
    hub2 = await setup_mikrotik_entry(
        hass,
        entry_2,
        wireless_data=[DEVICE_1_WIRELESS, DEVICE_2_WIRELESS],
        dhcp_data=[DEVICE_1_DHCP, DEVICE_2_DHCP],
    )

    assert DEVICE_1_WIRELESS["mac-address"] not in hub2.data
    assert DEVICE_2_WIRELESS["mac-address"] in hub2.data

    assert DEVICE_1_WIRELESS["mac-address"] in hass.data[DOMAIN][CLIENTS]
    assert DEVICE_2_WIRELESS["mac-address"] in hass.data[DOMAIN][CLIENTS]


async def test_arp_ping(hass: HomeAssistant) -> None:
    """Test arp ping devices to confirm they are connected."""

    hub_options = {
        "force_dhcp": True,
        CONF_ARP_PING: True,
        CONF_DHCP_SERVER_TRACK_MODE: "ARP ping",
        CONF_DETECTION_TIME: 200,
        CONF_SCAN_INTERVAL: 10,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA, options=hub_options)
    entry.add_to_hass(hass)

    # test device show as home if arp ping returns value
    await setup_mikrotik_entry(
        hass,
        entry,
        wireless_data=[],
        dhcp_data=[DEVICE_1_DHCP, DEVICE_2_DHCP],
        arp_data=ARP_DATA,
        ping_result=PING_SUCCESS,
    )
    assert hass.data[DOMAIN][CLIENTS]["00:00:00:00:00:01"].last_seen is not None
    # client has no active-address
    assert hass.data[DOMAIN][CLIENTS]["00:00:00:00:00:02"].last_seen is None


async def test_arp_ping_timeout(hass: HomeAssistant) -> None:
    """Test arp ping timeout to confirm if client is not connected."""

    hub_options = {
        "force_dhcp": True,
        CONF_ARP_PING: True,
        CONF_DHCP_SERVER_TRACK_MODE: "ARP ping",
        CONF_DETECTION_TIME: 200,
        CONF_SCAN_INTERVAL: 10,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA, options=hub_options)
    entry.add_to_hass(hass)

    await setup_mikrotik_entry(
        hass,
        entry,
        wireless_data=[],
        dhcp_data=[DEVICE_1_DHCP, DEVICE_2_DHCP],
        arp_data=ARP_DATA,
        ping_result=PING_FAIL,
    )
    assert hass.data[DOMAIN][CLIENTS]["00:00:00:00:00:01"].last_seen is None
    assert hass.data[DOMAIN][CLIENTS]["00:00:00:00:00:02"].last_seen is None


async def test_update_failed_conn_error(hass: HomeAssistant) -> None:
    """Test failing to connect during update."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(hass, entry)

    with patch.object(librouteros.Api, "__call__") as mock_api_call:
        mock_api_call.side_effect = librouteros.exceptions.ConnectionClosed()
        await hub.async_refresh()
        assert not hub.last_update_success


async def test_update_failed_auth_error(hass: HomeAssistant) -> None:
    """Test failing to connect during update."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(hass, entry)

    with patch.object(librouteros.Api, "__call__") as mock_api_call:
        mock_api_call.side_effect = [
            librouteros.exceptions.ConnectionClosed("bla"),
            librouteros.exceptions.TrapError("invalid user name or password"),
        ]
        with pytest.raises(ConfigEntryAuthFailed):
            await hub.async_update()
