"""Tests for the Tilt Pi coordinator."""

import aiohttp
import pytest

from homeassistant.components.tilt_pi.const import DOMAIN
from homeassistant.components.tilt_pi.coordinator import TiltPiDataUpdateCoordinator
from homeassistant.components.tilt_pi.model import TiltColor
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_HOST = "192.168.1.123"
TEST_PORT = 1880


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
        },
        unique_id="test123",
    )


async def test_coordinator_async_update_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
) -> None:
    """Test coordinator update with valid data."""
    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        json=[
            {
                "mac": "00:1A:2B:3C:4D:5E",
                "Color": "BLACK",
                "SG": 1.010,
                "Temp": "55.0",
            },
            {
                "mac": "00:1s:99:f1:d2:4f",
                "Color": "YELLOW",
                "SG": 1.015,
                "Temp": "68.0",
            },
        ],
    )

    coordinator = TiltPiDataUpdateCoordinator(hass, mock_entry)
    data = await coordinator._async_update_data()

    assert len(data) == 2
    black_tilt = data[0]
    assert black_tilt.color == TiltColor.BLACK
    assert black_tilt.mac_id == "00:1A:2B:3C:4D:5E"
    assert black_tilt.temperature == 55.0
    assert black_tilt.gravity == 1.010
    yellow_tilt = data[1]
    assert yellow_tilt.color == TiltColor.YELLOW
    assert yellow_tilt.mac_id == "00:1s:99:f1:d2:4f"
    assert yellow_tilt.temperature == 68.0
    assert yellow_tilt.gravity == 1.015


async def test_coordinator_async_update_data_empty_response(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
) -> None:
    """Test coordinator update with valid data."""
    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        json=[],
    )

    coordinator = TiltPiDataUpdateCoordinator(hass, mock_entry)
    data = await coordinator._async_update_data()

    assert len(data) == 0


async def test_coordinator_async_update_data_connection_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
) -> None:
    """Test coordinator handling connection error."""
    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        exc=aiohttp.ClientError,
    )

    coordinator = TiltPiDataUpdateCoordinator(hass, mock_entry)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_async_update_data_timeout_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
) -> None:
    """Test coordinator handling connection error."""
    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        exc=TimeoutError,
    )

    coordinator = TiltPiDataUpdateCoordinator(hass, mock_entry)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
