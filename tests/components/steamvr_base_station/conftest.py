"""SteamVR Base Station test fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from lighthouse_ble import BaseStationV2, DeviceInfo, LighthouseConnectionError
import pytest

from homeassistant.components.steamvr_base_station.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import STATION_SERVICE_INFO, TEST_ADDRESS, TEST_NAME

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info_bleak

DEVICE_INFO = DeviceInfo(
    model="1004",
    serial="FB92001DB6 V001017-20.A",
    firmware="R: 2.9.2004771 M: 1.8.2004742 B: 3.4.3782793",
    hardware="0.0",
    manufacturer="Valve Corp.",
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_set_power() -> Generator[AsyncMock]:
    """Mock sending a power command."""
    with patch.object(BaseStationV2, "set_power", autospec=True) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_read_device_info() -> Generator[AsyncMock]:
    """Mock reading the Device Information Service."""
    with patch.object(
        BaseStationV2, "read_device_info", autospec=True, return_value=DEVICE_INFO
    ) as mock:
        yield mock


@pytest.fixture
def device_info_unreachable(mock_read_device_info: AsyncMock) -> None:
    """Make reading the Device Information Service fail."""
    mock_read_device_info.side_effect = LighthouseConnectionError("out of range")


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the test station."""
    return MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_ADDRESS, title=TEST_NAME, data={}
    )


@pytest.fixture
def station_in_range(hass: HomeAssistant) -> None:
    """Make the station visible to Home Assistant's Bluetooth stack."""
    inject_bluetooth_service_info_bleak(hass, STATION_SERVICE_INFO)


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, station_in_range: None, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the integration for a station in range."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry
