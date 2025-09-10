"""Configuration for VeSync tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack
from itertools import chain
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest
from pyvesync import VeSync
from pyvesync.base_devices.bulb_base import VeSyncBulb
from pyvesync.base_devices.fan_base import VeSyncFanBase
from pyvesync.base_devices.humidifier_base import HumidifierState
from pyvesync.base_devices.outlet_base import VeSyncOutlet
from pyvesync.base_devices.switch_base import VeSyncSwitch
from pyvesync.const import HumidifierFeatures
from pyvesync.devices.vesynchumidifier import VeSyncHumid200S, VeSyncHumid200300S

from homeassistant.components.vesync import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .common import DEVICE_CATEGORIES, mock_multiple_device_responses

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def patch_vesync_firmware():
    """Patch VeSync to disable firmware checks."""
    with patch(
        "pyvesync.vesync.VeSync.check_firmware", new=AsyncMock(return_value=True)
    ):
        yield


@pytest.fixture(autouse=True)
def patch_vesync_login():
    """Patch VeSync login method."""
    with patch("pyvesync.vesync.VeSync.login", new=AsyncMock()):
        yield


@pytest.fixture(autouse=True)
def patch_vesync():
    """Patch VeSync methods and several properties/attributes for all tests."""
    props = {
        "enabled": True,
        "token": "TEST_TOKEN",
        "account_id": "TEST_ACCOUNT_ID",
    }

    with (
        patch.multiple(
            "pyvesync.vesync.VeSync",
            check_firmware=AsyncMock(return_value=True),
            login=AsyncMock(return_value=None),
        ),
        ExitStack() as stack,
    ):
        for name, value in props.items():
            mock = stack.enter_context(
                patch.object(VeSync, name, new_callable=PropertyMock)
            )
            mock.return_value = value
        yield


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


class _DevicesContainer:
    def __init__(self) -> None:
        for category in DEVICE_CATEGORIES:
            setattr(self, category, [])

        # wrap all devices in a read-only proxy array
        self._devices = MappingProxyType(
            {category: getattr(self, category) for category in DEVICE_CATEGORIES}
        )

    def __iter__(self) -> Iterator[_DevicesContainer]:
        return chain.from_iterable(getattr(self, c) for c in DEVICE_CATEGORIES)

    def __len__(self) -> int:
        return sum(len(getattr(self, c)) for c in DEVICE_CATEGORIES)

    def __bool__(self) -> bool:
        return any(getattr(self, c) for c in DEVICE_CATEGORIES)


@pytest.fixture(name="manager")
def manager_fixture():
    """Create a mock VeSync manager fixture."""
    devices = _DevicesContainer()

    mock_vesync = MagicMock(spec=VeSync)
    mock_vesync.update = AsyncMock()
    mock_vesync.devices = devices
    mock_vesync._dev_list = devices._devices

    mock_vesync.account_id = "account_id"
    mock_vesync.time_zone = "America/New_York"

    with patch("homeassistant.components.vesync.VeSync", return_value=mock_vesync):
        yield mock_vesync


@pytest.fixture(name="fan")
def fan_fixture():
    """Create a mock VeSync fan fixture."""
    return Mock(
        VeSyncFanBase,
        cid="fan",
        device_type="fan",
        device_name="Test Fan",
        device_status="on",
        modes=[],
        connection_status="online",
        current_firm_version="1.0.0",
    )


@pytest.fixture(name="bulb")
def bulb_fixture():
    """Create a mock VeSync bulb fixture."""
    return Mock(
        VeSyncBulb,
        cid="bulb",
        device_name="Test Bulb",
    )


@pytest.fixture(name="switch")
def switch_fixture():
    """Create a mock VeSync switch fixture."""
    return Mock(
        VeSyncSwitch,
        is_dimmable=Mock(return_value=False),
    )


@pytest.fixture(name="dimmable_switch")
def dimmable_switch_fixture():
    """Create a mock VeSync switch fixture."""
    return Mock(
        VeSyncSwitch,
        is_dimmable=Mock(return_value=True),
    )


@pytest.fixture(name="outlet")
def outlet_fixture():
    """Create a mock VeSync outlet fixture."""
    return Mock(
        VeSyncOutlet,
        cid="outlet",
        device_name="Test Outlet",
    )


@pytest.fixture(name="humidifier")
def humidifier_fixture():
    """Create a mock VeSync Classic 200S humidifier fixture."""
    return Mock(
        VeSyncHumid200S,
        cid="200s-humidifier",
        config={
            "auto_target_humidity": 40,
            "display": "true",
            "automatic_stop": "true",
        },
        features=[HumidifierFeatures.NIGHTLIGHT],
        device_type="Classic200S",
        device_name="Humidifier 200s",
        device_status="on",
        mist_modes=["auto", "manual"],
        mist_levels=[1, 2, 3, 4, 5, 6],
        sub_device_no=0,
        target_minmax=(30, 80),
        state=Mock(
            HumidifierState,
            connection_status="online",
            humidity=50,
            mist_level=6,
            mode=None,
            nightlight_status="dim",
            nightlight_brightness=50,
            water_lacks=False,
            water_tank_lifted=False,
        ),
        connection_status="online",
        current_firm_version="1.0.0",
    )


@pytest.fixture(name="humidifier_300s")
def humidifier_300s_fixture():
    """Create a mock VeSync Classic 300S humidifier fixture."""
    return Mock(
        VeSyncHumid200300S,
        cid="300s-humidifier",
        config={
            "auto_target_humidity": 40,
            "display": "true",
            "automatic_stop": "true",
        },
        features=[HumidifierFeatures.NIGHTLIGHT],
        device_type="Classic300S",
        device_name="Humidifier 300s",
        device_status="on",
        mist_modes=["auto", "manual"],
        mist_levels=[1, 2, 3, 4, 5, 6],
        sub_device_no=0,
        target_minmax=(30, 80),
        state=Mock(
            HumidifierState,
            connection_status="online",
            humidity=50,
            mist_level=6,
            mode=None,
            nightlight_status="dim",
            nightlight_brightness=50,
            water_lacks=False,
            water_tank_lifted=False,
        ),
        config_module="configModule",
        current_firm_version="1.0.0",
    )


@pytest.fixture(name="humidifier_config_entry")
async def humidifier_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config
) -> MockConfigEntry:
    """Create a mock VeSync config entry for `Humidifier 200s`."""
    entry = MockConfigEntry(
        title="VeSync",
        domain=DOMAIN,
        data=config[DOMAIN],
    )
    entry.add_to_hass(hass)

    device_name = "Humidifier 200s"
    mock_multiple_device_responses(aioclient_mock, [device_name])
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
    manager._dev_list["humidifiers"].append(request.getfixturevalue(request.param))
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(name="fan_config_entry")
async def fan_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config
) -> MockConfigEntry:
    """Create a mock VeSync config entry for `SmartTowerFan`."""
    entry = MockConfigEntry(
        title="VeSync",
        domain=DOMAIN,
        data=config[DOMAIN],
    )
    entry.add_to_hass(hass)

    device_name = "SmartTowerFan"
    mock_multiple_device_responses(aioclient_mock, [device_name])
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="switch_old_id_config_entry")
async def switch_old_id_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config
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

    mock_multiple_device_responses(aioclient_mock, [wall_switch, humidifer])

    return entry
