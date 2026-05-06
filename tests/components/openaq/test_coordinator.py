"""Test OpenAQ data coordinator helpers."""

from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from homeassistant.components.openaq.coordinator import (
    HomeAssistantOpenAQTransport,
    OpenAQMeasurement,
    async_create_openaq_client,
    create_openaq_client,
    get_openaq_value,
    normalize_latest_measurements,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)
from homeassistant.core import HomeAssistant

from .conftest import make_latest, make_sensor


async def test_transport_sends_request_with_shared_httpx_client() -> None:
    """Test the transport sends requests with the shared httpx client."""
    response = httpx.Response(
        200,
        json={"results": []},
        request=httpx.Request("GET", "https://api.openaq.org/v3/locations"),
    )
    httpx_client = AsyncMock(spec=httpx.AsyncClient)
    httpx_client.request.return_value = response

    transport = HomeAssistantOpenAQTransport(httpx_client)

    assert (
        await transport.send_request(
            "GET",
            "https://api.openaq.org/v3/locations",
            params={"limit": 1},
            headers={"X-API-Key": "api-key"},
        )
        is response
    )
    httpx_client.request.assert_awaited_once_with(
        method="GET",
        url="https://api.openaq.org/v3/locations",
        params={"limit": 1},
        headers={"X-API-Key": "api-key"},
    )


async def test_create_openaq_client_keeps_shared_httpx_client_open() -> None:
    """Test closing the OpenAQ client does not close the shared httpx client."""
    httpx_client = httpx.AsyncClient()
    client = create_openaq_client("api-key", httpx_client)

    try:
        assert client.transport.client is httpx_client
        await client.close()
        assert not httpx_client.is_closed
    finally:
        await httpx_client.aclose()


async def test_async_create_openaq_client_uses_shared_httpx_client(
    hass: HomeAssistant,
) -> None:
    """Test creating an OpenAQ client from Home Assistant."""
    httpx_client = httpx.AsyncClient()

    try:
        with patch(
            "homeassistant.components.openaq.coordinator.get_async_client",
            return_value=httpx_client,
        ):
            client = await async_create_openaq_client(hass, "api-key")

        assert client.transport.client is httpx_client
        await client.close()
    finally:
        await httpx_client.aclose()


def test_get_openaq_value_dict() -> None:
    """Test getting OpenAQ values from dict data."""
    data = {"id": 123}

    assert get_openaq_value(data, "id") == 123
    assert get_openaq_value(data, "missing") is None


def test_normalize_latest_measurements_ignores_invalid_data() -> None:
    """Test normalizing latest measurements ignores invalid API data."""
    measurements = normalize_latest_measurements(
        [
            make_latest("1", 8.5),
            make_latest("unknown", 12.1),
            make_latest(999, 44.1),
            make_latest(2, True),
            make_latest(3, 33.2),
        ],
        [
            make_sensor("1", "pm2.5", "µg/m3"),
            make_sensor(2, "pm10"),
            make_sensor(3, "no_units", 123),
            SimpleNamespace(id=4, parameter=SimpleNamespace()),
        ],
    )

    assert measurements == MappingProxyType(
        {
            "pm25": OpenAQMeasurement(
                parameter="pm25",
                value=8.5,
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            ),
            "nounits": OpenAQMeasurement(
                parameter="nounits",
                value=33.2,
                unit=None,
            ),
        }
    )


def test_normalize_latest_measurements_uses_sensor_latest() -> None:
    """Test normalizing measurements from sensor latest data."""
    measurements = normalize_latest_measurements(
        [],
        [make_sensor(1, "pm10", "mg/m3", value=12.1)],
    )

    assert measurements == MappingProxyType(
        {
            "pm10": OpenAQMeasurement(
                parameter="pm10",
                value=12.1,
                unit=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
            )
        }
    )
