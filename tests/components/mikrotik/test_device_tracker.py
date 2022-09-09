"""The tests for the Mikrotik device tracker platform."""
from datetime import timedelta

from freezegun import freeze_time
import pytest

from homeassistant.components import mikrotik
import homeassistant.components.device_tracker as device_tracker
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from . import (
    DEVICE_2_WIRELESS,
    DEVICE_3_DHCP_NUMERIC_NAME,
    DEVICE_3_WIRELESS,
    DHCP_DATA,
    MOCK_DATA,
    MOCK_OPTIONS,
    WIRELESS_DATA,
    setup_mikrotik_entry,
)

from tests.common import MockConfigEntry, async_fire_time_changed, patch


@pytest.fixture
def mock_device_registry_devices(hass):
    """Create device registry devices so the device tracker entities are enabled."""
    dev_reg = dr.async_get(hass)
    config_entry = MockConfigEntry(domain="something_else")

    for idx, device in enumerate(
        (
            "00:00:00:00:00:01",
            "00:00:00:00:00:02",
            "00:00:00:00:00:03",
        )
    ):
        dev_reg.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )


def mock_command(self, cmd, params=None):
    """Mock the Mikrotik command method."""
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIRELESS]:
        return True
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP]:
        return DHCP_DATA
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.WIRELESS]:
        return WIRELESS_DATA
    return {}


async def test_device_trackers(hass, mock_device_registry_devices):
    """Test device_trackers created by mikrotik."""

    # test devices are added from wireless list only
    await setup_mikrotik_entry(hass)

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "home"
    assert device_1.attributes["ip"] == "0.0.0.1"
    assert "ip_address" not in device_1.attributes
    assert device_1.attributes["mac"] == "00:00:00:00:00:01"
    assert device_1.attributes["host_name"] == "Device_1"
    assert "mac_address" not in device_1.attributes
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2 is None

    with patch.object(mikrotik.hub.MikrotikData, "command", new=mock_command):
        # test device_2 is added after connecting to wireless network
        WIRELESS_DATA.append(DEVICE_2_WIRELESS)

        async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done()

        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2 is not None
        assert device_2.state == "home"
        assert device_2.attributes["ip"] == "0.0.0.2"
        assert "ip_address" not in device_2.attributes
        assert device_2.attributes["mac"] == "00:00:00:00:00:02"
        assert "mac_address" not in device_2.attributes
        assert device_2.attributes["host_name"] == "Device_2"

        # test state remains home if last_seen  consider_home_interval
        del WIRELESS_DATA[1]  # device 2 is removed from wireless list
        with freeze_time(utcnow() + timedelta(minutes=4)):
            async_fire_time_changed(hass, utcnow() + timedelta(minutes=4))
            await hass.async_block_till_done()

        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2.state == "home"

        # test state changes to away if last_seen > consider_home_interval
        with freeze_time(utcnow() + timedelta(minutes=6)):
            async_fire_time_changed(hass, utcnow() + timedelta(minutes=6))
            await hass.async_block_till_done()

        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2.state == "not_home"


async def test_force_dhcp(hass, mock_device_registry_devices):
    """Test updating hub that supports wireless with forced dhcp method."""

    # hub supports wireless by default, force_dhcp is enabled to override
    await setup_mikrotik_entry(hass, force_dhcp=False)
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == "home"
    # device_2 is not on the wireless list but it is still added from DHCP
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "home"


async def test_hub_not_support_wireless(hass, mock_device_registry_devices):
    """Test device_trackers created when hub doesn't support wireless."""

    await setup_mikrotik_entry(hass, support_wireless=False)
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == "home"
    # device_2 is added from DHCP
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "home"


async def test_arp_ping_success(hass, mock_device_registry_devices):
    """Test arp ping devices to confirm they are connected."""

    with patch.object(mikrotik.hub.MikrotikData, "do_arp_ping", return_value=True):
        await setup_mikrotik_entry(hass, arp_ping=True, force_dhcp=True)

        # test wired device_2 show as home if arp ping returns True
        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2
        assert device_2.state == "home"


async def test_arp_ping_timeout(hass, mock_device_registry_devices):
    """Test arp ping timeout so devices are shown away."""
    with patch.object(mikrotik.hub.MikrotikData, "do_arp_ping", return_value=False):
        await setup_mikrotik_entry(hass, arp_ping=True, force_dhcp=True)

        # test wired device_2 show as not_home if arp ping times out
        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2
        assert device_2.state == "not_home"


async def test_device_trackers_numerical_name(hass, mock_device_registry_devices):
    """Test device_trackers created by mikrotik with numerical device name."""

    await setup_mikrotik_entry(
        hass, dhcp_data=[DEVICE_3_DHCP_NUMERIC_NAME], wireless_data=[DEVICE_3_WIRELESS]
    )

    device_3 = hass.states.get("device_tracker.123")
    assert device_3 is not None
    assert device_3.state == "home"
    assert device_3.attributes["friendly_name"] == "123"
    assert device_3.attributes["ip"] == "0.0.0.3"
    assert "ip_address" not in device_3.attributes
    assert device_3.attributes["mac"] == "00:00:00:00:00:03"
    assert device_3.attributes["host_name"] == 123
    assert "mac_address" not in device_3.attributes


async def test_restoring_devices(hass):
    """Test restoring existing device_tracker entities if not detected on startup."""
    config_entry = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS
    )
    config_entry.add_to_hass(hass)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        device_tracker.DOMAIN,
        mikrotik.DOMAIN,
        "00:00:00:00:00:01",
        suggested_object_id="device_1",
        config_entry=config_entry,
    )
    registry.async_get_or_create(
        device_tracker.DOMAIN,
        mikrotik.DOMAIN,
        "00:00:00:00:00:02",
        suggested_object_id="device_2",
        config_entry=config_entry,
    )
    registry.async_get_or_create(
        device_tracker.DOMAIN,
        mikrotik.DOMAIN,
        "00:00:00:00:00:03",
        suggested_object_id="device_3",
        config_entry=config_entry,
    )

    await setup_mikrotik_entry(hass)

    # test device_2 which is not in wireless list is restored
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "home"
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2 is not None
    assert device_2.state == "not_home"
    # device_3 is not on the DHCP list or wireless list
    # so it won't be restored.
    device_3 = hass.states.get("device_tracker.device_3")
    assert device_3 is None


async def test_update_failed(hass, mock_device_registry_devices):
    """Test failing to connect during update."""

    await setup_mikrotik_entry(hass)

    with patch.object(
        mikrotik.hub.MikrotikData, "command", side_effect=mikrotik.errors.CannotConnect
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done()

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == STATE_UNAVAILABLE
