"""Validate city metadata and coordinate lookup requests."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientSession
import pytest

from homeassistant.components.xiaomi_weather.api import (
    LOCATION_URL,
    Location,
    XiaomiLocationClient,
    XiaomiWeatherError,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.test_util.aiohttp import AiohttpClientMocker

CITY = {
    "locationKey": "weathercn:101010100",
    "name": "北京市",
    "affiliation": "中国",
    "latitude": "39.904",
    "longitude": "116.408",
    "status": 0,
}


async def test_lookup_http(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Send the expected query and deduplicate returned cities."""
    aioclient_mock.get(
        f"{LOCATION_URL}/geo",
        params={"latitude": "39.9", "longitude": "116.4", "locale": "zh_cn"},
        json=[CITY, CITY],
    )
    session = async_get_clientsession(hass)
    result = await XiaomiLocationClient(session).async_locate(39.9, 116.4)
    assert result == [Location("101010100", "北京市", "中国")]
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        [None],
        [{}],
        [{**CITY, "name": ""}],
        [{**CITY, "locationKey": "weathercn:bad"}],
        [{**CITY, "affiliation": None}],
    ],
)
async def test_bad_location(payload: object) -> None:
    """Test bad location."""
    with (
        patch(
            "homeassistant.components.xiaomi_weather.api._async_get_json",
            return_value=payload,
        ),
        pytest.raises(XiaomiWeatherError),
    ):
        await XiaomiLocationClient(AsyncMock(spec=ClientSession)).async_locate(
            39.9, 116.4
        )


async def test_unsupported_and_failed_locations() -> None:
    """Test unsupported and failed locations."""
    with patch(
        "homeassistant.components.xiaomi_weather.api._async_get_json",
        return_value=[{**CITY, "locationKey": "accu:123"}, {**CITY, "status": 1}],
    ):
        assert (
            await XiaomiLocationClient(AsyncMock(spec=ClientSession)).async_locate(
                39.9, 116.4
            )
            == []
        )


@pytest.mark.parametrize(
    "valid_cities",
    [pytest.param([], id="all-failed"), pytest.param([CITY], id="mixed-results")],
)
async def test_failed_location_without_key(
    valid_cities: list[dict[str, str | int]],
) -> None:
    """Skip status-only failures while preserving valid location results."""
    with patch(
        "homeassistant.components.xiaomi_weather.api._async_get_json",
        return_value=[{"status": 1}, *valid_cities],
    ):
        result = await XiaomiLocationClient(AsyncMock(spec=ClientSession)).async_locate(
            39.9, 116.4
        )
    assert result == [Location("101010100", "北京市", "中国") for _ in valid_cities]
