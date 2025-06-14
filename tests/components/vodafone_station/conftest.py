"""Configure tests for Vodafone Station."""

from datetime import UTC, datetime

from aiovodafone import VodafoneStationDevice
import pytest

from homeassistant.components.vodafone_station.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import DEVICE_1_HOST, DEVICE_1_MAC, DEVICE_2_MAC

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
            "homeassistant.components.vodafone_station.coordinator.VodafoneStationSercommApi",
            autospec=True,
        ) as mock_router,
        patch(
            "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi",
            new=mock_router,
        ),
    ):
        router = mock_router.return_value
        router.get_devices_data.return_value = {
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
        router.get_sensor_data.return_value = load_json_object_fixture(
            "get_sensor_data.json", DOMAIN
        )
        router.convert_uptime.return_value = datetime(
            2024, 11, 19, 20, 19, 0, tzinfo=UTC
        )
        router.base_url = "https://fake_host"
        yield router


@pytest.fixture
def mock_config_entry() -> Generator[MockConfigEntry]:
    """Mock a Vodafone Station config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "fake_host",
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
