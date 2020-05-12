"""The tests for the Mikrotik device tracker platform."""
from datetime import timedelta
from itertools import cycle

from homeassistant.components import mikrotik
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import (
    DEVICE_1_WIRELESS,
    DEVICE_3_DHCP,
    DEVICE_3_WIRELESS,
    HUB1_WIRELESS_DATA,
    HUB2_WIRELESS_DATA,
    MOCK_HUB1,
    MOCK_HUB2,
)
from .test_hub import DATA_RETURN, setup_mikrotik_integration

from tests.async_mock import patch


async def test_platform_manually_configured(hass):
    """Test that nothing happens when configuring mikrotik through device tracker platform."""
    assert not (
        await async_setup_component(
            hass,
            DEVICE_TRACKER_DOMAIN,
            {DEVICE_TRACKER_DOMAIN: {"platform": "mikrotik"}},
        )
    )
    assert mikrotik.DOMAIN not in hass.data


async def test_wireless_device_trackers(hass, api):
    """Test device_trackers created by mikrotik."""
    i = cycle([0, 1])
    hub_index = 0

    def mock_command(self, cmd, params=None):
        nonlocal i
        nonlocal hub_index

        # check for first cmd by each hub and set hub_index accordingly
        if cmd in [
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IDENTITY],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP],
        ]:
            hub_index = next(i)
        return DATA_RETURN[cmd][hub_index]

    # test devices are added from wireless list only
    mikrotik_mock = await setup_mikrotik_integration(hass, support_wireless=True)

    # test device_1 is added from HUB1
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "home"
    # test device_2 is added from HUB2
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2 is not None
    assert device_1.state == "home"
    # test device_3 is not added because it is not connected yet
    device_3 = hass.states.get("device_tracker.device_3")
    assert device_3 is None

    with patch.object(mikrotik.hub.MikrotikHub, "command", new=mock_command):
        # test device_3 is added after connecting to wireless network
        HUB1_WIRELESS_DATA.append(DEVICE_3_WIRELESS)
        await mikrotik_mock.async_update()
        await hass.async_block_till_done()

        device_3 = hass.states.get("device_tracker.device_3")
        assert device_3 is not None
        assert device_3.state == "home"

        # test state remains home if last_seen < consider_home_interval
        del HUB1_WIRELESS_DATA[1]  # device_3 is removed from wireless list
        mikrotik_mock.clients[
            "00:00:00:00:00:03"
        ]._last_seen = dt_util.utcnow() - timedelta(minutes=4)
        hass.helpers.dispatcher.async_dispatcher_send(mikrotik_mock.signal_data_update)
        await hass.async_block_till_done()

        device_3 = hass.states.get("device_tracker.device_3")
        assert device_3.state == "home"

        # test state changes to away if last_seen > consider_home_interval
        mikrotik_mock.clients[
            "00:00:00:00:00:03"
        ]._last_seen = dt_util.utcnow() - timedelta(minutes=5)
        hass.helpers.dispatcher.async_dispatcher_send(mikrotik_mock.signal_data_update)
        await hass.async_block_till_done()

        device_3 = hass.states.get("device_tracker.device_3")
        assert device_3.state == "not_home"


async def test_device_trackers_from_dhcp(hass, api):
    """Test device_trackers updated from DHCP server created by mikrotik."""
    i = cycle([0, 1])
    hub_index = 0

    def mock_command(self, cmd, params=None):
        nonlocal i
        nonlocal hub_index

        # check for first cmd by each hub and set hub_index accordingly
        if cmd in [
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IDENTITY],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP],
        ]:
            hub_index = next(i)
        return DATA_RETURN[cmd][hub_index]

    # test devices are added from wireless list only
    mikrotik_mock = await setup_mikrotik_integration(hass)

    # test device_1 is added from HUB1
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "home"
    # test device_2 is added from HUB2
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2 is not None
    assert device_1.state == "home"
    # test device_3 is added but showing away
    device_3 = hass.states.get("device_tracker.device_3")
    assert device_3 is not None
    assert device_3.state == "not_home"
    # test device_4 is added and showing home
    device_4 = hass.states.get("device_tracker.device_4")
    assert device_4 is not None
    assert device_4.state == "home"

    with patch.object(mikrotik.hub.MikrotikHub, "command", new=mock_command):
        # test device_3 is added after connecting to hub
        DEVICE_3_DHCP["active-address"] = "0.0.0.3"
        await mikrotik_mock.async_update()
        await hass.async_block_till_done()

        device_3 = hass.states.get("device_tracker.device_3")
        assert device_3 is not None
        assert device_3.state == "home"

        # test state remains home if last_seen < consider_home_interval
        DEVICE_3_DHCP.pop("active-address")
        mikrotik_mock.clients[
            "00:00:00:00:00:03"
        ]._last_seen = dt_util.utcnow() - timedelta(minutes=4)
        hass.helpers.dispatcher.async_dispatcher_send(mikrotik_mock.signal_data_update)
        await hass.async_block_till_done()

        device_3 = hass.states.get("device_tracker.device_3")
        assert device_3.state == "home"

        # test state changes to away if last_seen > consider_home_interval
        mikrotik_mock.clients[
            "00:00:00:00:00:03"
        ]._last_seen = dt_util.utcnow() - timedelta(minutes=5)
        hass.helpers.dispatcher.async_dispatcher_send(mikrotik_mock.signal_data_update)
        await hass.async_block_till_done()

        device_3 = hass.states.get("device_tracker.device_3")
        assert device_3.state == "not_home"


async def test_device_tracker_switching_hubs(hass, api):
    """Test device tracker moving to another hub."""
    i = cycle([0, 1])
    hub_index = 0

    def mock_command(self, cmd, params=None):
        nonlocal i
        nonlocal hub_index

        # check for first cmd by each hub and set hub_index accordingly
        if cmd in [
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IDENTITY],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP],
        ]:
            hub_index = next(i)
        return DATA_RETURN[cmd][hub_index]

    mikrotik_mock = await setup_mikrotik_integration(hass, support_wireless=True)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    hub1_device = device_registry.async_get_device(
        {(mikrotik.DOMAIN, MOCK_HUB1[CONF_HOST])}, set()
    )
    hub2_device = device_registry.async_get_device(
        {(mikrotik.DOMAIN, MOCK_HUB2[CONF_HOST])}, set()
    )

    # device_1 is initially connected to HUB1
    this_device = device_registry.async_get_device(
        {(mikrotik.DOMAIN, "00:00:00:00:00:01")}, set()
    )
    assert this_device.via_device_id == hub1_device.id

    with patch.object(mikrotik.hub.MikrotikHub, "command", new=mock_command):
        # device_1 is still connected connected to HUB1 after update
        await mikrotik_mock.async_update()
        hass.helpers.dispatcher.async_dispatcher_send(mikrotik_mock.signal_data_update)
        await hass.async_block_till_done()
        this_device = device_registry.async_get_device(
            {(mikrotik.DOMAIN, "00:00:00:00:00:01")}, set()
        )
        assert this_device.via_device_id == hub1_device.id

        # device_1 is disconnected from HUB1 and connected to HUB2
        del HUB1_WIRELESS_DATA[0]
        HUB2_WIRELESS_DATA.append(DEVICE_1_WIRELESS)

        await mikrotik_mock.async_update()
        hass.helpers.dispatcher.async_dispatcher_send(mikrotik_mock.signal_data_update)
        await hass.async_block_till_done()
        this_device = device_registry.async_get_device(
            {(mikrotik.DOMAIN, "00:00:00:00:00:01")}, set()
        )
        assert this_device.via_device_id == hub2_device.id

    # revert the changes made for this test
    del HUB2_WIRELESS_DATA[1]
    HUB1_WIRELESS_DATA.append(DEVICE_1_WIRELESS)
