"""Tests for the RFM Gateway API client."""

from __future__ import annotations

from aiohttp import ClientError
import pytest

from homeassistant.components import rfm_gateway
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker

BASE_URL = "http://192.0.2.10"


async def test_get_capabilities_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test fetching capabilities successfully."""
    aioclient_mock.get(
        f"{BASE_URL}/api/rf/capabilities",
        json={
            "device_name": "RFM Gateway",
            "supported_frequency_ranges": [[433050000, 434790000]],
            "supported_modulations": ["ook"],
        },
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)
    capabilities = await client.async_get_capabilities()

    assert capabilities.device_name == "RFM Gateway"
    assert capabilities.supported_frequency_ranges == [(433050000, 434790000)]
    assert capabilities.supported_modulations == ["ook"]


async def test_get_capabilities_invalid_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test invalid capabilities payload handling."""
    aioclient_mock.get(
        f"{BASE_URL}/api/rf/capabilities",
        json={
            "device_name": "RFM Gateway",
            "supported_frequency_ranges": [],
            "supported_modulations": ["ook"],
        },
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayProtocolError):
        await client.async_get_capabilities()


async def test_get_capabilities_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test timeout handling when fetching capabilities."""
    aioclient_mock.get(
        f"{BASE_URL}/api/rf/capabilities",
        exc=TimeoutError(),
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayConnectionError):
        await client.async_get_capabilities()


async def test_get_capabilities_error_status(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test protocol error when capabilities endpoint returns non-200."""
    aioclient_mock.get(
        f"{BASE_URL}/api/rf/capabilities",
        status=500,
        text="boom",
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayProtocolError):
        await client.async_get_capabilities()


async def test_get_capabilities_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test client transport error handling when fetching capabilities."""
    aioclient_mock.get(
        f"{BASE_URL}/api/rf/capabilities",
        exc=ClientError("network down"),
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayConnectionError):
        await client.async_get_capabilities()


async def test_get_capabilities_payload_must_be_dict(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test protocol error when capabilities payload is not an object."""
    aioclient_mock.get(
        f"{BASE_URL}/api/rf/capabilities",
        json=[1, 2, 3],
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayProtocolError):
        await client.async_get_capabilities()


async def test_get_capabilities_modulations_must_be_list(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test protocol error when supported_modulations is not a list."""
    aioclient_mock.get(
        f"{BASE_URL}/api/rf/capabilities",
        json={
            "device_name": "RFM Gateway",
            "supported_frequency_ranges": [[433050000, 434790000]],
            "supported_modulations": "ook",
        },
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayProtocolError):
        await client.async_get_capabilities()


async def test_get_capabilities_empty_modulations_defaults_to_ook(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test empty modulation values fall back to default modulation."""
    aioclient_mock.get(
        f"{BASE_URL}/api/rf/capabilities",
        json={
            "device_name": "RFM Gateway",
            "supported_frequency_ranges": [[433050000, 434790000]],
            "supported_modulations": ["", "   "],
        },
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)
    capabilities = await client.async_get_capabilities()

    assert capabilities.supported_modulations == ["ook"]


async def test_send_raw_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test sending raw RF command successfully."""
    aioclient_mock.post(
        f"{BASE_URL}/api/rf/transmit",
        json={"ok": True},
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    await client.async_send_raw(
        frequency_hz=433920000,
        modulation="ook",
        repeat_count=2,
        timings_us=[350, 1050, 350, 350],
    )


async def test_send_raw_success_with_non_json_response(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test sending raw RF command with non-JSON success response."""
    aioclient_mock.post(
        f"{BASE_URL}/api/rf/transmit",
        status=200,
        text="ok",
        headers={"Content-Type": "text/plain"},
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    await client.async_send_raw(
        frequency_hz=433920000,
        modulation="ook",
        repeat_count=2,
        timings_us=[350, 1050, 350, 350],
    )


async def test_send_raw_error_status(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test failed raw RF transmit request."""
    aioclient_mock.post(
        f"{BASE_URL}/api/rf/transmit",
        status=400,
        text="parameter error",
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayProtocolError):
        await client.async_send_raw(
            frequency_hz=433920000,
            modulation="ook",
            repeat_count=1,
            timings_us=[350, 1050, 350, 350],
        )


async def test_send_raw_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test timeout handling when sending raw RF command."""
    aioclient_mock.post(
        f"{BASE_URL}/api/rf/transmit",
        exc=TimeoutError(),
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayConnectionError):
        await client.async_send_raw(
            frequency_hz=433920000,
            modulation="ook",
            repeat_count=1,
            timings_us=[350, 1050, 350, 350],
        )


async def test_send_raw_gateway_ok_false_without_error_field(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test fallback protocol message when gateway returns ok=false."""
    aioclient_mock.post(
        f"{BASE_URL}/api/rf/transmit",
        json={"ok": False},
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayProtocolError):
        await client.async_send_raw(
            frequency_hz=433920000,
            modulation="ook",
            repeat_count=1,
            timings_us=[350, 1050, 350, 350],
        )


async def test_send_raw_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test transport error handling while sending raw RF."""
    aioclient_mock.post(
        f"{BASE_URL}/api/rf/transmit",
        exc=ClientError("socket error"),
    )

    client = rfm_gateway.RfmGatewayClient(hass=hass, base_url=BASE_URL)

    with pytest.raises(rfm_gateway.RfmGatewayConnectionError):
        await client.async_send_raw(
            frequency_hz=433920000,
            modulation="ook",
            repeat_count=1,
            timings_us=[350, 1050, 350, 350],
        )


def test_parse_ranges_filters_invalid_values() -> None:
    """Test parse_ranges skips malformed and invalid range entries."""
    parse_ranges = rfm_gateway.RfmGatewayClient._parse_ranges

    assert parse_ranges("not-a-list") == []
    assert parse_ranges([["x", 2], [10, 1], [0, 10], [100, 200, 300]]) == []
    assert parse_ranges([[100, 200], (300, 400)]) == [(100, 200), (300, 400)]
