"""Configuration for VeSync tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pyvesync import VeSync
from pyvesync.base_devices.bulb_base import VeSyncBulb
from pyvesync.base_devices.fan_base import VeSyncFanBase
from pyvesync.base_devices.outlet_base import VeSyncOutlet
from pyvesync.base_devices.switch_base import VeSyncSwitch
import requests_mock

from homeassistant.components.vesync import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .common import mock_multiple_device_responses

from tests.common import MockConfigEntry


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

    devices = set()
    outlets = set()
    switches = set()
    fans = set()
    bulbs = set()
    humidifers = set()

    # If you need to support .outlets, .switches, etc. on devices, use a MagicMock
    devices_container = MagicMock()
    devices_container.__iter__.side_effect = lambda: iter(devices)
    devices_container.__contains__.side_effect = devices.__contains__
    devices_container.__len__.side_effect = devices.__len__
    devices_container.add.side_effect = devices.add
    devices_container.discard.side_effect = devices.discard
    devices_container.outlets = outlets
    devices_container.switches = switches
    devices_container.fans = fans
    devices_container.bulbs = bulbs
    devices_container.humidifers = humidifers

    mock_vesync = Mock(VeSync)
    mock_vesync.login = AsyncMock(return_value=True)
    mock_vesync.update = AsyncMock()
    mock_vesync.devices = devices_container
    mock_vesync._dev_list = {
        "fans": fans,
        "outlets": outlets,
        "switches": switches,
        "bulbs": bulbs,
    }
    mock_vesync.account_id = "account_id"
    mock_vesync.time_zone = "America/New_York"

    with patch("homeassistant.components.vesync.VeSync", return_value=mock_vesync):
        yield mock_vesync


@pytest.fixture(name="fan")
def fan_fixture():
    """Create a mock VeSync fan fixture."""
    return Mock(VeSyncFanBase)


@pytest.fixture(name="bulb")
def bulb_fixture():
    """Create a mock VeSync bulb fixture."""
    return Mock(VeSyncBulb)


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
    return Mock(VeSyncOutlet)


@pytest.fixture(name="humidifier")
def humidifier_fixture():
    """Create a mock VeSync Classic200S humidifier fixture."""
    return Mock(
        VeSyncFanBase,
        cid="200s-humidifier",
        config={
            "auto_target_humidity": 40,
            "display": "true",
            "automatic_stop": "true",
        },
        details={
            "humidity": 35,
            "mode": "manual",
        },
        device_type="Classic200S",
        device_name="Humidifier 200s",
        device_status="on",
        mist_level=6,
        mist_modes=["auto", "manual"],
        mode=None,
        sub_device_no=0,
        config_module="configModule",
        connection_status="online",
        current_firm_version="1.0.0",
        water_lacks=False,
        water_tank_lifted=False,
    )


@pytest.fixture(name="humidifier_300s")
def humidifier_300s_fixture():
    """Create a mock VeSync Classic300S humidifier fixture."""
    return Mock(
        VeSyncFanBase,
        cid="300s-humidifier",
        config={
            "auto_target_humidity": 40,
            "display": "true",
            "automatic_stop": "true",
        },
        details={"humidity": 35, "mode": "manual", "night_light_brightness": 50},
        device_type="Classic300S",
        device_name="Humidifier 300s",
        device_status="on",
        mist_level=6,
        mist_modes=["auto", "manual"],
        mode=None,
        night_light=True,
        sub_device_no=0,
        config_module="configModule",
        connection_status="online",
        current_firm_version="1.0.0",
        water_lacks=False,
        water_tank_lifted=False,
    )


@pytest.fixture(name="humidifier_config_entry")
async def humidifier_config_entry(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, config
) -> MockConfigEntry:
    """Create a mock VeSync config entry for `Humidifier 200s`."""
    entry = MockConfigEntry(
        title="VeSync",
        domain=DOMAIN,
        data=config[DOMAIN],
    )
    entry.add_to_hass(hass)

    device_name = "Humidifier 200s"
    mock_multiple_device_responses(requests_mock, [device_name])
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture
async def install_humidifier_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager,
    request: pytest.FixtureRequest,
) -> None:
    """Create a mock VeSync config entry with the specified humidifier device."""

    # Install the defined humidifier
    manager._dev_list["fans"].append(request.getfixturevalue(request.param))
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(name="fan_config_entry")
async def fan_config_entry(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, config
) -> MockConfigEntry:
    """Create a mock VeSync config entry for `SmartTowerFan`."""
    entry = MockConfigEntry(
        title="VeSync",
        domain=DOMAIN,
        data=config[DOMAIN],
    )
    entry.add_to_hass(hass)

    device_name = "SmartTowerFan"
    mock_multiple_device_responses(requests_mock, [device_name])
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="switch_old_id_config_entry")
async def switch_old_id_config_entry(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, config
) -> MockConfigEntry:
    """Create a mock VeSync config entry for `switch` with the old unique ID approach."""
    entry = MockConfigEntry(
        title="VeSync",
        domain=DOMAIN,
        data=config[DOMAIN],
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    wall_switch = "Wall Switch"
    humidifer = "Humidifier 200s"

    mock_multiple_device_responses(requests_mock, [wall_switch, humidifer])

    return entry
