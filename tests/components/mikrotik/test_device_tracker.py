"""The tests for the Mikrotik device tracker platform."""
from datetime import timedelta

from homeassistant.components import mikrotik
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.mikrotik.const import CLIENTS, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from . import (
    DEVICE_1_DHCP,
    DEVICE_1_WIRELESS,
    DEVICE_2_DHCP,
    DEVICE_2_WIRELESS,
    DHCP_DATA,
    MOCK_DATA,
    MOCK_OPTIONS,
    WIRELESS_DATA,
)
from .test_hub import setup_mikrotik_entry

from tests.common import MockConfigEntry, patch

DEFAULT_DETECTION_TIME = timedelta(seconds=300)


def mock_command(self, cmd, params=None):
    """Mock the Mikrotik command method."""
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_CAPSMAN]:
        return True
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIRELESS]:
        return True
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP]:
        return DHCP_DATA
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.CAPSMAN]:
        return WIRELESS_DATA
    if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.WIRELESS]:
        return WIRELESS_DATA
    return {}


async def test_device_trackers(hass: HomeAssistant, legacy_patchable_time) -> None:
    """Test device_trackers created by mikrotik."""

    # test devices are added from wireless list only
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(hass, entry)

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

    with patch.object(mikrotik.hub.MikrotikHubData, "command", new=mock_command):
        # test device_2 is added after connecting to wireless network
        WIRELESS_DATA.append(DEVICE_2_WIRELESS)

        await hub.async_refresh()
        await hass.async_block_till_done()

        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2 is not None
        assert device_2.state == "home"
        assert device_2.attributes["ip"] == "0.0.0.2"
        assert "ip_address" not in device_2.attributes
        assert device_2.attributes["mac"] == "00:00:00:00:00:02"
        assert "mac_address" not in device_2.attributes
        assert device_2.attributes["host_name"] == "Device_2"

        # test state remains home if last_seen < consider_home_interval
        del WIRELESS_DATA[1]  # device 2 is removed from wireless list
        hass.data[DOMAIN][CLIENTS][
            "00:00:00:00:00:02"
        ]._last_seen = dt_util.utcnow() - timedelta(minutes=4)
        await hub.async_refresh()
        await hass.async_block_till_done()

        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2
        assert device_2.state == "home"

        # test state changes to away if last_seen > consider_home_interval
        hass.data[DOMAIN][CLIENTS][
            "00:00:00:00:00:02"
        ]._last_seen = dt_util.utcnow() - timedelta(minutes=5)
        await hub.async_refresh()
        await hass.async_block_till_done()

        device_2 = hass.states.get("device_tracker.device_2")
        assert device_2
        assert device_2.state == "not_home"


async def test_restoring_devices(hass):
    """Test restoring existing device_tracker entities if not detected on startup."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS
    )
    entry.add_to_hass(hass)

    registry = er.async_get(hass)
    registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        "00:00:00:00:00:01",
        suggested_object_id="device_1",
        config_entry=entry,
    )
    registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        "00:00:00:00:00:02",
        suggested_object_id="device_2",
        config_entry=entry,
    )

    await setup_mikrotik_entry(hass, entry, wireless_data=[DEVICE_1_WIRELESS])

    # test device_2 which is not in wireless list is restored
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "home"
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2 is not None
    assert device_2.state == "not_home"


async def test_client_detected_by_different_hub(
    hass: HomeAssistant,
) -> None:
    """Hub should not add clients initially registered by other hub entries."""

    # setup hub 1
    entry_1 = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS
    )
    entry_1.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        "00:00:00:00:00:01",
        suggested_object_id="device_1",
        config_entry=entry_1,
    )
    registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        "00:00:00:00:00:02",
        suggested_object_id="device_2",
        config_entry=entry_1,
    )

    hub1 = await setup_mikrotik_entry(
        hass,
        entry_1,
        wireless_data=[],
        dhcp_data=[DEVICE_1_DHCP, DEVICE_2_DHCP],
    )

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "not_home"

    # setup hub 2
    hub2_data = {
        CONF_HOST: "0.0.0.2",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_PORT: 8279,
        CONF_VERIFY_SSL: True,
    }
    entry_2 = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=hub2_data, options=MOCK_OPTIONS
    )
    entry_2.add_to_hass(hass)
    await setup_mikrotik_entry(
        hass,
        entry_2,
        wireless_data=[DEVICE_1_WIRELESS],
        dhcp_data=[DEVICE_1_DHCP, DEVICE_2_DHCP],
    )
    # the device will be updated on the next hub1 refresh
    await hub1.async_refresh()
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == "home"
    device_registry = dr.async_get(hass)
    hub2_device = device_registry.async_get_device({(DOMAIN, "0.0.0.2")}, set())
    client_device = device_registry.async_get_device(
        {(DOMAIN, "00:00:00:00:00:01")}, set()
    )
    assert hub2_device is not None
    assert client_device is not None
    assert client_device.via_device_id == hub2_device.id
