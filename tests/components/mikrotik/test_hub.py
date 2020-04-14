"""Test Mikrotik hub."""
# from copy import copy
import itertools

from asynctest import patch
import librouteros
import pytest

from homeassistant import config_entries
from homeassistant.components import mikrotik
from homeassistant.components.mikrotik import const
from homeassistant.exceptions import ConfigEntryNotReady

from . import (
    ENTRY_DATA,
    ENTRY_OPTIONS,
    HUB1_ARP_DATA,
    HUB1_DHCP_DATA,
    HUB1_IDENTITY,
    HUB1_INFO,
    HUB1_WIRELESS_DATA,
    HUB2_ARP_DATA,
    HUB2_DHCP_DATA,
    HUB2_IDENTITY,
    HUB2_INFO,
    HUB2_WIRELESS_DATA,
    MOCK_HUB1,
    MOCK_HUB2,
    MOCK_OPTIONS,
)

from tests.common import MockConfigEntry

DATA_RETURN = {
    const.MIKROTIK_SERVICES[const.IDENTITY]: [HUB1_IDENTITY, HUB2_IDENTITY],
    const.MIKROTIK_SERVICES[const.INFO]: [HUB1_INFO, HUB2_INFO],
    const.MIKROTIK_SERVICES[const.CAPSMAN]: [HUB1_WIRELESS_DATA, HUB2_WIRELESS_DATA],
    const.MIKROTIK_SERVICES[const.WIRELESS]: [HUB1_WIRELESS_DATA, HUB2_WIRELESS_DATA],
    const.MIKROTIK_SERVICES[const.DHCP]: [HUB1_DHCP_DATA, HUB2_DHCP_DATA],
    const.MIKROTIK_SERVICES[const.ARP]: [HUB1_ARP_DATA, HUB2_ARP_DATA],
}


async def setup_mikrotik_integration(
    hass,
    config_entry=None,
    entry_data=ENTRY_DATA,
    config_options=ENTRY_OPTIONS,
    support_capsman=False,
    support_wireless=False,
):
    """Set up Mikrotik intergation successfully."""
    i = itertools.cycle([0, 1])
    hub_index = 0

    def mock_command(self, cmd, params=None):
        nonlocal i
        nonlocal hub_index
        if cmd == const.MIKROTIK_SERVICES[const.IS_CAPSMAN]:
            return support_capsman
        if cmd == const.MIKROTIK_SERVICES[const.IS_WIRELESS]:
            return support_wireless

        # check for first cmd by each hub and set hub_index accordingly
        if cmd in [
            const.MIKROTIK_SERVICES[const.IDENTITY],
            const.MIKROTIK_SERVICES[const.DHCP],
        ]:
            hub_index = next(i)
        return DATA_RETURN[cmd][hub_index]

    if not config_entry:
        config_entry = MockConfigEntry(
            domain=mikrotik.DOMAIN, data=dict(ENTRY_DATA), options=dict(config_options),
        )
        config_entry.add_to_hass(hass)

    with patch.object(mikrotik.hub.MikrotikHub, "command", new=mock_command):

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        if (
            mikrotik.DOMAIN not in hass.data
            or config_entry.entry_id not in hass.data[mikrotik.DOMAIN]
        ):
            return None

        return hass.data[mikrotik.DOMAIN][config_entry.entry_id]


async def test_all_hubs_fail(hass, api):
    """Test all hubs failing to connect."""
    api.side_effect = librouteros.exceptions.LibRouterosError

    await setup_mikrotik_integration(hass)

    assert mikrotik.DOMAIN not in hass.data


async def test_hubs_conn_error(hass, api):
    """Test hubs connection errors."""

    # if hub raises LoginError it is not added
    # if hub raises CannotConnect it is still added but not available
    api.side_effect = [
        librouteros.exceptions.LibRouterosError("invalid user name or password"),
        librouteros.exceptions.LibRouterosError,
    ]
    config_entry = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=dict(ENTRY_DATA), options=dict(ENTRY_OPTIONS),
    )
    config_entry.add_to_hass(hass)

    mikrotik_mock = mikrotik.Mikrotik(hass, config_entry)
    with pytest.raises(ConfigEntryNotReady):
        await mikrotik_mock.async_setup()

        assert len(mikrotik_mock.hubs) == 1
        assert MOCK_HUB1[const.CONF_HOST] not in mikrotik_mock.hubs
        assert MOCK_HUB2[const.CONF_HOST] in mikrotik_mock.hubs
        assert config_entry.state == config_entries.ENTRY_STATE_SETUP_ERROR


async def test_update_failed(hass, api):
    """Test failing to connect during update."""

    mikrotik_mock = await setup_mikrotik_integration(hass)
    assert mikrotik_mock.hubs[MOCK_HUB1[mikrotik.CONF_HOST]].available is True

    with patch.object(
        mikrotik.hub.MikrotikHub, "command", side_effect=mikrotik.errors.CannotConnect
    ):
        await mikrotik_mock.async_update()
        await hass.async_block_till_done()

        assert mikrotik_mock.hubs[MOCK_HUB1[mikrotik.CONF_HOST]].available is False


async def test_hub_support_capsman(hass, api):
    """Test updating clients when hub supports CAPSMAN."""

    mikrotik_mock = await setup_mikrotik_integration(hass, support_capsman=True)

    assert mikrotik_mock.clients["00:00:00:00:00:01"]._params == HUB1_DHCP_DATA[0]
    assert (
        mikrotik_mock.clients["00:00:00:00:00:01"]._wireless_params
        == HUB1_WIRELESS_DATA[0]
    )
    assert mikrotik_mock.clients["00:00:00:00:00:02"]._params == HUB2_DHCP_DATA[0]
    assert (
        mikrotik_mock.clients["00:00:00:00:00:02"]._wireless_params
        == HUB2_WIRELESS_DATA[0]
    )


async def test_hub_support_wireless(hass, api):
    """Test updating clients when hub supports WIRELESS."""

    mikrotik_mock = await setup_mikrotik_integration(hass, support_wireless=True)

    assert mikrotik_mock.clients["00:00:00:00:00:01"]._params == HUB1_DHCP_DATA[0]
    assert (
        mikrotik_mock.clients["00:00:00:00:00:01"]._wireless_params
        == HUB1_WIRELESS_DATA[0]
    )
    assert mikrotik_mock.clients["00:00:00:00:00:02"]._params == HUB2_DHCP_DATA[0]
    assert (
        mikrotik_mock.clients["00:00:00:00:00:02"]._wireless_params
        == HUB2_WIRELESS_DATA[0]
    )


async def test_hub_dhcp_fallback(hass, api):
    """Test updating clients when hub doesn't support CAPSMAN or WIRELESS."""

    mikrotik_mock = await setup_mikrotik_integration(hass)

    assert mikrotik_mock.clients["00:00:00:00:00:01"]._params == HUB1_DHCP_DATA[0]
    assert mikrotik_mock.clients["00:00:00:00:00:01"]._wireless_params is None
    assert mikrotik_mock.clients["00:00:00:00:00:02"]._params == HUB2_DHCP_DATA[0]
    assert mikrotik_mock.clients["00:00:00:00:00:02"]._wireless_params is None


async def test_force_dhcp(hass, api):
    """Test updating hub devices with forced dhcp method."""

    mikrotik_mock = await setup_mikrotik_integration(
        hass,
        config_options={**MOCK_OPTIONS, mikrotik.CONF_FORCE_DHCP: True},
        support_wireless=True,
    )

    assert mikrotik_mock.hubs[MOCK_HUB1[mikrotik.CONF_HOST]].support_wireless is True
    assert mikrotik_mock.clients["00:00:00:00:00:01"]._params == HUB1_DHCP_DATA[0]
    assert (
        mikrotik_mock.clients["00:00:00:00:00:01"]._wireless_params
        == HUB1_WIRELESS_DATA[0]
    )

    # devices not in wireless list are added from dhcp
    assert mikrotik_mock.clients["00:00:00:00:00:03"]._params == HUB1_DHCP_DATA[1]
    assert mikrotik_mock.clients["00:00:00:00:00:03"]._wireless_params is None


async def test_arp_ping_pinging(hass, api):
    """Test arp ping devices to confirm they are connected."""

    with patch.object(mikrotik.hub.MikrotikHub, "do_arp_ping", return_value=True):
        mikrotik_mock = await setup_mikrotik_integration(
            hass,
            config_options={
                **MOCK_OPTIONS,
                mikrotik.CONF_FORCE_DHCP: True,
                mikrotik.CONF_ARP_PING: True,
            },
        )
    # client last_seen is updated because device is pinging
    assert mikrotik_mock.clients["00:00:00:00:00:01"].last_seen is not None
    assert mikrotik_mock.clients["00:00:00:00:00:02"].last_seen is not None


async def test_arp_ping_timeout(hass, api):
    """Test arp ping devices to confirm they are connected."""
    with patch.object(mikrotik.hub.MikrotikHub, "do_arp_ping", return_value=False):
        mikrotik_mock = await setup_mikrotik_integration(
            hass,
            config_options={
                **MOCK_OPTIONS,
                mikrotik.CONF_FORCE_DHCP: True,
                mikrotik.CONF_ARP_PING: True,
            },
        )
    # client last_seen is None because device is not pinging
    assert mikrotik_mock.clients["00:00:00:00:00:01"].last_seen is None
    assert mikrotik_mock.clients["00:00:00:00:00:02"].last_seen is None


async def test_get_api_handle_errors(hass, api):
    """Check that get_api can handle librouteros errors."""
    api.side_effect = [
        librouteros.exceptions.LibRouterosError("invalid user name or password"),
        librouteros.exceptions.LibRouterosError,
    ]
    # test login error
    with pytest.raises(mikrotik.errors.LoginError):
        await mikrotik.hub.get_api(hass, MOCK_HUB1)

    # test connection error
    with pytest.raises(mikrotik.errors.CannotConnect):
        await mikrotik.hub.get_api(hass, MOCK_HUB1)
