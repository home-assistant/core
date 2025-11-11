"""Configure tests for Vodafone Station."""

from datetime import UTC, datetime

from aiovodafone.api import VodafoneStationCommonApi, VodafoneStationDevice
import pytest
from yarl import URL

from homeassistant.components.vodafone_station.const import (
    CONF_DEVICE_DETAILS,
    DEVICE_TYPE,
    DEVICE_URL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import (
    DEVICE_1_HOST,
    DEVICE_1_MAC,
    DEVICE_2_MAC,
    TEST_HOST,
    TEST_PASSWORD,
    TEST_TYPE,
    TEST_URL,
    TEST_USERNAME,
)

from tests.common import (
    AsyncMock,
    Generator,
    MockConfigEntry,
    load_json_object_fixture,
    patch,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.vodafone_station.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_vodafone_station_router() -> Generator[AsyncMock]:
    """Mock a Vodafone Station router."""
    with (
        patch(
            "homeassistant.components.vodafone_station.coordinator.init_api_class",
            autospec=True,
        ) as mock_router,
        patch(
            "homeassistant.components.vodafone_station.config_flow.init_api_class",
            new=mock_router,
        ),
        patch.object(
            VodafoneStationCommonApi,
            "get_device_type",
            new=AsyncMock(return_value=(TEST_TYPE, URL(TEST_URL))),
        ),
    ):
        router = mock_router.return_value
        router.login = AsyncMock(return_value=True)
        router.logout = AsyncMock(return_value=True)
        router.get_devices_data = AsyncMock(
            return_value={
                DEVICE_1_MAC: VodafoneStationDevice(
                    connected=True,
                    connection_type="wifi",
                    ip_address="192.168.1.10",
                    name=DEVICE_1_HOST,
                    mac=DEVICE_1_MAC,
                    type="laptop",
                    wifi="2.4G",
                ),
                DEVICE_2_MAC: VodafoneStationDevice(
                    connected=False,
                    connection_type="lan",
                    ip_address="192.168.1.11",
                    name="LanDevice1",
                    mac=DEVICE_2_MAC,
                    type="desktop",
                    wifi="",
                ),
            }
        )
        router.get_sensor_data = AsyncMock(
            return_value=load_json_object_fixture("get_sensor_data.json", DOMAIN)
        )
        router.convert_uptime.return_value = datetime(
            2024, 11, 19, 20, 19, 0, tzinfo=UTC
        )
        router.base_url = URL(TEST_URL)
        router.restart_connection = AsyncMock(return_value=True)
        router.restart_router = AsyncMock(return_value=True)

        yield router


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Vodafone Station config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_DEVICE_DETAILS: {
                DEVICE_TYPE: TEST_TYPE,
                DEVICE_URL: TEST_URL,
            },
        },
        version=1,
        minor_version=2,
    )
