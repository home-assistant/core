"""Validate city metadata and the three actual lookup request shapes."""

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


@pytest.mark.parametrize(
    ("endpoint", "query", "method", "args"),
    [
        pytest.param(
            "info",
            {"locationKey": "weathercn:101010100", "locale": "zh_cn"},
            "async_city",
            ("101010100",),
            id="city-code",
        ),
        pytest.param(
            "geo",
            {"latitude": "39.9", "longitude": "116.4", "locale": "zh_cn"},
            "async_locate",
            (39.9, 116.4),
            id="coordinates",
        ),
        pytest.param(
            "search",
            {"name": "北京", "locale": "zh_cn"},
            "async_search",
            ("北京",),
            id="city-name",
        ),
    ],
)
async def test_lookup_http(
    hass: HomeAssistant,
    endpoint: str,
    query: dict[str, str],
    method: str,
    args: tuple[str | float, ...],
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Send the expected query and deduplicate returned cities."""
    aioclient_mock.get(f"{LOCATION_URL}/{endpoint}", params=query, json=[CITY, CITY])
    session = async_get_clientsession(hass)
    result = await getattr(XiaomiLocationClient(session), method)(*args)
    assert result == [Location("101010100", "北京市", "中国", 39.904, 116.408)]
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        [None],
        [{}],
        [{**CITY, "latitude": "NaN"}],
        [{**CITY, "longitude": "190"}],
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
        await XiaomiLocationClient(AsyncMock(spec=ClientSession)).async_search("北京")


async def test_unsupported_and_failed_locations() -> None:
    """Test unsupported and failed locations."""
    with patch(
        "homeassistant.components.xiaomi_weather.api._async_get_json",
        return_value=[{**CITY, "locationKey": "accu:123"}, {**CITY, "status": 1}],
    ):
        assert (
            await XiaomiLocationClient(AsyncMock(spec=ClientSession)).async_search(
                "北京"
            )
            == []
        )


async def test_wrong_city_match() -> None:
    """Test wrong city match."""
    with patch(
        "homeassistant.components.xiaomi_weather.api._async_get_json",
        return_value=[CITY],
    ):
        assert (
            await XiaomiLocationClient(AsyncMock(spec=ClientSession)).async_city(
                "101020100"
            )
            == []
        )
