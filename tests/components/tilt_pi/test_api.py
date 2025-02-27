"""Test the Tilt Pi API client."""

import aiohttp
import pytest

from homeassistant.components.tilt_pi.api import (
    TiltPiClient,
    TiltPiConnectionError,
    TiltPiConnectionTimeoutError,
)
from homeassistant.core import HomeAssistant

from .conftest import TEST_HOST, TEST_PORT

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_get_hydrometers(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tiltpi_api_all_response: list[dict],
) -> None:
    """Test getting hydrometer data."""
    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        json=tiltpi_api_all_response,
    )

    api = TiltPiClient(
        host=TEST_HOST,
        port=TEST_PORT,
        session=aioclient_mock.create_session(hass.loop),
    )
    data = await api.get_hydrometers()

    assert len(data) == 1
    assert data[0].mac_id == "00:1A:2B:3C:4D:5E"
    assert data[0].color == "Red"
    assert data[0].temperature == 68.5
    assert data[0].gravity == 1.052


async def test_get_hydrometers_timeout(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test timeout while getting hydrometer data."""
    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        exc=TimeoutError,
    )

    api = TiltPiClient(
        host=TEST_HOST,
        port=TEST_PORT,
        session=aioclient_mock.create_session(hass.loop),
    )
    with pytest.raises(TiltPiConnectionTimeoutError):
        await api.get_hydrometers()


async def test_get_hydrometers_connection_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test connection error while getting hydrometer data."""
    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        exc=aiohttp.ClientError,
    )

    api = TiltPiClient(
        host=TEST_HOST,
        port=TEST_PORT,
        session=aioclient_mock.create_session(hass.loop),
    )
    with pytest.raises(TiltPiConnectionError):
        await api.get_hydrometers()
