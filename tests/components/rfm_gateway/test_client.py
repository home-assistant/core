"""Tests for the RFM Gateway API client."""

from __future__ import annotations

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
