"""Configuration for VeSync tests."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from pyvesync import VeSync
from pyvesync.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.vesyncbulb import VeSyncBulb
from pyvesync.vesyncfan import VeSyncAirBypass
from pyvesync.vesyncoutlet import VeSyncOutlet
from pyvesync.vesyncswitch import VeSyncSwitch

from homeassistant.components.vesync import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
async def setup_platform(
    hass: HomeAssistant, config_entry: ConfigEntry, config: ConfigType
):
    """Set up the vesync platform."""
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant, config) -> ConfigEntry:
    """Create a mock VeSync config entry."""
    entry = MockConfigEntry(
        title="VeSync",
        domain=DOMAIN,
        data=config[DOMAIN],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture() -> ConfigType:
    """Create hass config fixture."""
    return {DOMAIN: {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}}


@pytest.fixture(name="manager")
def manager_fixture() -> VeSync:
    """Create a mock VeSync manager fixture."""

    outlets = []
    switches = []
    fans = []
    bulbs = []

    mock_vesync = Mock(VeSync)
    mock_vesync.login = Mock(return_value=True)
    mock_vesync.update = Mock()
    mock_vesync.outlets = outlets
    mock_vesync.switches = switches
    mock_vesync.fans = fans
    mock_vesync.bulbs = bulbs
    mock_vesync._dev_list = {
        "fans": fans,
        "outlets": outlets,
        "switches": switches,
        "bulbs": bulbs,
    }
    mock_vesync.account_id = "account_id"
    mock_vesync.time_zone = "America/New_York"
    mock = Mock(return_value=mock_vesync)

    with patch("homeassistant.components.vesync.VeSync", new=mock):
        yield mock_vesync


@pytest.fixture(name="manager_devices")
def manager_with_devices_fixture(fan, bulb, switch, dimmable_switch, outlet) -> VeSync:
    """Create a mock VeSync manager fixture."""

    outlets = [outlet]
    switches = [switch, dimmable_switch]
    fans = [fan]
    bulbs = [bulb]

    mock_vesync = Mock(VeSync)
    mock_vesync.login = Mock(return_value=True)
    mock_vesync.update = Mock()
    mock_vesync.outlets = outlets
    mock_vesync.switches = switches
    mock_vesync.fans = fans
    mock_vesync.bulbs = bulbs
    mock_vesync._dev_list = {
        "fans": fans,
        "outlets": outlets,
        "switches": switches,
        "bulbs": bulbs,
    }
    mock_vesync.account_id = "account_id"
    mock_vesync.time_zone = "America/New_York"
    mock = Mock(return_value=mock_vesync)

    with patch("homeassistant.components.vesync.VeSync", new=mock):
        yield mock_vesync


@pytest.fixture(name="base_device")
def veync_base_device_fixture() -> VeSyncBaseDevice:
    """Create a mock VeSyncBaseDevice fixture."""
    mock_fixture = Mock(VeSyncBaseDevice)
    mock_fixture.cid = "cid"
    mock_fixture.current_firm_version = 0
    mock_fixture.connection_status = "online"
    mock_fixture.device_image = "device image"
    mock_fixture.device_name = "device name"
    mock_fixture.device_status = "on"
    mock_fixture.device_type = "device type"
    mock_fixture.is_on = True
    mock_fixture.sub_device_no = 1
    mock_fixture.turn_on = Mock()
    mock_fixture.turn_off = Mock()
    mock_fixture.update = Mock()
    mock_fixture.uuid = "uuid"

    config = {}
    mock_fixture.config = config

    config_dict = {}
    mock_fixture.config_dict = config_dict

    details = {}
    mock_fixture.details = details

    return mock_fixture


@pytest.fixture(name="fan")
def fan_fixture():
    """Create a mock VeSync fan fixture."""
    mock_fixture = Mock(VeSyncAirBypass)
    return mock_fixture


@pytest.fixture(name="bulb")
def bulb_fixture():
    """Create a mock VeSync bulb fixture."""
    mock_fixture = Mock(VeSyncBulb)
    return mock_fixture


@pytest.fixture(name="switch")
def switch_fixture():
    """Create a mock VeSync switch fixture."""
    mock_fixture = Mock(VeSyncSwitch)
    mock_fixture.is_dimmable = Mock(return_value=False)
    return mock_fixture


@pytest.fixture(name="dimmable_switch")
def dimmable_switch_fixture():
    """Create a mock VeSync switch fixture."""
    mock_fixture = Mock(VeSyncSwitch)
    mock_fixture.is_dimmable = Mock(return_value=True)
    return mock_fixture


@pytest.fixture(name="outlet")
def outlet_fixture():
    """Create a mock VeSync outlet fixture."""
    mock_fixture = Mock(VeSyncOutlet)
    return mock_fixture


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock):
    """Fixture to build the various responses for the Helpers.call_api method."""
    # This fixture provides a variety of handlers for the various vesync API calls
    # However, the "https://smartapi.vesync.com/cloud/v1/deviceManaged/devices" URL
    # must be explicitly added by the test case to ensure that the correct devices
    # are loaded.
    #
    # For example:
    # requests_mock.post(
    #     "https://smartapi.vesync.com/cloud/v1/deviceManaged/devices",
    #     json=load_json_object_fixture("vesync-devices.json", DOMAIN),
    # )
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/user/login",
        json=load_json_object_fixture("vesync-login.json", DOMAIN),
    )
    requests_mock.get(
        "https://smartapi.vesync.com/v1/device/outlet/detail",
        json=load_json_object_fixture("outlet-detail.json", DOMAIN),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/dimmer/v1/device/devicedetail",
        json=load_json_object_fixture("dimmer-detail.json", DOMAIN),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/SmartBulb/v1/device/devicedetail",
        json=load_json_object_fixture("device-detail.json", DOMAIN),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/deviceManaged/bypass",
        json=load_json_object_fixture("device-detail.json", DOMAIN),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v2/deviceManaged/bypassV2",
        json=load_json_object_fixture("device-detail.json", DOMAIN),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/131airPurifier/v1/device/deviceDetail",
        json=load_json_object_fixture("purifier-detail.json", DOMAIN),
    )
