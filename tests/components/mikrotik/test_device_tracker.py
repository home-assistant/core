"""The tests for the Mikrotik device tracker platform."""

from datetime import timedelta
from typing import Any

from freezegun import freeze_time
import pytest

from homeassistant.components import device_tracker, mikrotik
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from . import setup_mikrotik_entry
from .conftest import MockConfigEntryFactory
from .const import (
    DEVICE_1_DHCP,
    DEVICE_1_WIRELESS,
    DEVICE_2_DHCP,
    DEVICE_2_WIRELESS,
    DEVICE_3_DHCP_NUMERIC_NAME,
    DEVICE_3_WIRELESS,
    DEVICE_4_DHCP,
    DEVICE_4_WIFIWAVE2,
    DHCP_DATA,
    MOCK_DATA,
    MOCK_OPTIONS,
    UPDATE_DATA,
    WIRELESS_DATA,
)

from tests.common import async_fire_time_changed, patch


@pytest.fixture
def mock_device_registry_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntryFactory,
) -> None:
    """Create device registry devices so the device tracker entities are enabled."""
    config_entry = mock_config_entry(domain="something_else", data={})
    config_entry.add_to_hass(hass)

    for idx, device in enumerate(
        (
            "00:00:00:00:00:01",
            "00:00:00:00:00:02",
            "00:00:00:00:00:03",
            "00:00:00:00:00:04",
        )
    ):
        device_registry.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )


def mock_command(
    self,
    cmd: str,
    params: dict[str, Any] | None = None,
    suppress_errors: bool = False,
    during_setup: bool = False,
) -> Any:
    """Mock the Mikrotik command method."""
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIRELESS]:
        return True
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP]:
        return DHCP_DATA
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.WIRELESS]:
        return WIRELESS_DATA
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.UPDATE]:
        return UPDATE_DATA
    return {}


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_device_trackers(hass: HomeAssistant) -> None:
    """Test device_trackers created by mikrotik."""

    # test devices are added from wireless list only
    await setup_mikrotik_entry(hass)

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == "home"
    assert device_1.attributes["ip"] == "0.0.0.1"
    assert device_1.attributes["mac"] == "00:00:00:00:00:01"
    assert device_1.attributes["host_name"] == "Device_1"
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2 is None

    with patch.object(mikrotik.coordinator.MikrotikData, "command", new=mock_command):
        # test device_2 is added after connecting to wireless network
        WIRELESS_DATA.append(DEVICE_2_WIRELESS)

        async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done(wait_background_tasks=True)

        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2
        assert device_2.state == "home"
        assert device_2.attributes["ip"] == "0.0.0.2"
        assert device_2.attributes["mac"] == "00:00:00:00:00:02"
        assert device_2.attributes["host_name"] == "Device_2"

        # test state remains home if last_seen within consider_home_interval
        del WIRELESS_DATA[1]  # device 2 is removed from wireless list
        with freeze_time(utcnow() + timedelta(minutes=4)):
            async_fire_time_changed(hass, utcnow() + timedelta(minutes=4))
            await hass.async_block_till_done(wait_background_tasks=True)

        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2
        assert device_2.state == "home"

        # test state changes to away if last_seen past consider_home_interval
        with freeze_time(utcnow() + timedelta(minutes=6)):
            async_fire_time_changed(hass, utcnow() + timedelta(minutes=6))
            await hass.async_block_till_done(wait_background_tasks=True)

        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2
        assert device_2.state == "not_home"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_force_dhcp(hass: HomeAssistant) -> None:
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


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_hub_not_support_wireless(hass: HomeAssistant) -> None:
    """Test device_trackers created when hub doesn't support wireless."""

    await setup_mikrotik_entry(hass, support_wireless=False)
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == "home"
    # device_2 is added from DHCP
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "home"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_hub_capsman(hass: HomeAssistant) -> None:
    """Test device_trackers created when hub is a CAPsMAN manager."""

    await setup_mikrotik_entry(
        hass,
        dhcp_data=[DEVICE_1_DHCP],
        support_wireless=False,
        support_capsman=True,
        capsman_data=[DEVICE_1_WIRELESS],
    )

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == "home"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_hub_wifi(hass: HomeAssistant) -> None:
    """Test device_trackers created when hub supports the legacy wifi driver."""

    await setup_mikrotik_entry(
        hass,
        dhcp_data=[DEVICE_2_DHCP],
        support_wireless=False,
        support_wifi=True,
        wifi_data=[DEVICE_2_WIRELESS],
    )

    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "home"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_hub_wireless_and_wifi(hass: HomeAssistant) -> None:
    """Test a hub exposing both the legacy wireless package and the wifi driver.

    The legacy ``wireless`` package can linger on a hub acting as a CAPsMAN for
    ``wifi`` access points, leaving its registration table empty while the
    connected clients are only listed on the ``wifi`` interface.
    """
    device_2_without_active_address = {
        key: value for key, value in DEVICE_2_DHCP.items() if key != "active-address"
    }

    await setup_mikrotik_entry(
        hass,
        dhcp_data=[DEVICE_1_DHCP, device_2_without_active_address],
        support_wireless=True,
        wireless_data=[],
        support_wifi=True,
        wifi_data=[DEVICE_2_WIRELESS],
    )

    # device_2 is only present on the wifi interface, not in the wireless list
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "home"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_wired_device_without_active_address_is_not_home(
    hass: HomeAssistant,
) -> None:
    """Test a wired device without an active-address is marked away."""
    device_without_active_address = {
        key: value for key, value in DEVICE_2_DHCP.items() if key != "active-address"
    }

    await setup_mikrotik_entry(
        hass,
        support_wireless=False,
        dhcp_data=[DEVICE_1_DHCP, device_without_active_address],
    )

    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "not_home"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_arp_ping_success(hass: HomeAssistant) -> None:
    """Test arp ping devices to confirm they are connected."""
    ping_replies = [{"seq": "0"}, {"seq": "1"}, {"seq": "2"}]

    await setup_mikrotik_entry(
        hass, arp_ping=True, force_dhcp=True, ping_data=ping_replies
    )

    # test wired device_2 shows as home if at least one arp ping reply is received
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "home"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_arp_ping_timeout(hass: HomeAssistant) -> None:
    """Test arp ping timeout so devices are shown away."""
    ping_replies = [
        {"status": "timeout"},
        {"status": "timeout"},
        {"status": "timeout"},
    ]

    await setup_mikrotik_entry(
        hass, arp_ping=True, force_dhcp=True, ping_data=ping_replies
    )

    # test wired device_2 shows as not_home if every arp ping reply times out
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "not_home"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_device_trackers_numerical_name(hass: HomeAssistant) -> None:
    """Test device_trackers created by mikrotik with numerical device name."""

    await setup_mikrotik_entry(
        hass, dhcp_data=[DEVICE_3_DHCP_NUMERIC_NAME], wireless_data=[DEVICE_3_WIRELESS]
    )

    device_3 = hass.states.get("device_tracker.123")
    assert device_3
    assert device_3.state == "home"
    assert device_3.attributes["friendly_name"] == "123 123"
    assert device_3.attributes["ip"] == "0.0.0.3"
    assert device_3.attributes["mac"] == "00:00:00:00:00:03"
    assert device_3.attributes["host_name"] == "123"


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_hub_wifiwave2(hass: HomeAssistant) -> None:
    """Test device_trackers created when hub supports wifiwave2."""

    await setup_mikrotik_entry(
        hass,
        dhcp_data=[DEVICE_4_DHCP],
        wifiwave2_data=[DEVICE_4_WIFIWAVE2],
        support_wireless=False,
        support_wifiwave2=True,
    )

    device_4 = hass.states.get("device_tracker.device_4")
    assert device_4
    assert device_4.state == "home"
    assert device_4.attributes["friendly_name"] == "Device_4 Device_4"
    assert device_4.attributes["ip"] == "0.0.0.4"
    assert device_4.attributes["mac"] == "00:00:00:00:00:04"
    assert device_4.attributes["host_name"] == "Device_4"


async def test_restoring_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntryFactory,
) -> None:
    """Test restoring existing device_tracker entities if not detected on startup."""
    config_entry = mock_config_entry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
        options=MOCK_OPTIONS,
    )
    config_entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        mikrotik.DOMAIN,
        "00:00:00:00:00:01",
        suggested_object_id="device_1",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        mikrotik.DOMAIN,
        "00:00:00:00:00:02",
        suggested_object_id="device_2",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
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


@pytest.mark.usefixtures("mock_device_registry_devices")
async def test_update_failed(hass: HomeAssistant) -> None:
    """Test failing to connect during update."""

    await setup_mikrotik_entry(hass)

    with patch.object(
        mikrotik.coordinator.MikrotikData,
        "command",
        side_effect=mikrotik.errors.CannotConnect,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done(wait_background_tasks=True)

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == STATE_UNAVAILABLE
