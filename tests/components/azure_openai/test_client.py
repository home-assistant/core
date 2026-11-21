"""Test Azure OpenAI client configuration."""

from unittest.mock import patch

import httpx
import pytest

from homeassistant.components.azure_openai.client import (
    create_classic_deployment_client,
)
from homeassistant.components.azure_openai.const import CONF_BASE_URL
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("base_url", "expected_prefix"),
    [
        (
            "https://example.openai.azure.com/openai/v1/",
            "https://example.openai.azure.com",
        ),
        (
            "https://gateway.example.com/azure-openai/openai/v1/",
            "https://gateway.example.com/azure-openai",
        ),
    ],
)
async def test_create_classic_deployment_client(
    hass: HomeAssistant,
    base_url: str,
    expected_prefix: str,
) -> None:
    """Test classic deployment requests use Azure routing and authentication."""
    requests: list[httpx.Request] = []

    async def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"text": "Transcribed"}, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle_request)
    ) as http_client:
        with patch(
            "homeassistant.components.azure_openai.client.get_async_client",
            return_value=http_client,
        ):
            client = create_classic_deployment_client(
                hass,
                {
                    CONF_API_KEY: "test-key",
                    CONF_BASE_URL: base_url,
                },
                "stt-deployment",
                "2025-03-01-preview",
            )

            await client.audio.transcriptions.create(
                model="stt-deployment",
                file=("audio.wav", b"RIFF"),
                response_format="json",
            )

    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == (
        f"{expected_prefix}/openai/deployments/"
        "stt-deployment/audio/transcriptions?api-version=2025-03-01-preview"
    )
    assert request.headers["api-key"] == "test-key"
    assert "authorization" not in request.headers
