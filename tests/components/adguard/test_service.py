"""Tests for the AdGuard Home sensor entities."""

from unittest.mock import patch

import pytest

from homeassistant.components.adguard.const import (
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_service_registration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard services be registered."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, aioclient_mock)

    services = hass.services.async_services_for_domain(DOMAIN)

    assert len(services) == 5
    assert SERVICE_ADD_URL in services
    assert SERVICE_DISABLE_URL in services
    assert SERVICE_ENABLE_URL in services
    assert SERVICE_REFRESH in services
    assert SERVICE_REMOVE_URL in services


async def test_service_unregistration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard services be unregistered with unloading last entry."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, aioclient_mock)

    services = hass.services.async_services_for_domain(DOMAIN)
    assert len(services) == 5

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    services = hass.services.async_services_for_domain(DOMAIN)
    assert len(services) == 0


@pytest.mark.parametrize(
    ("service", "mocked_requests", "service_call_data"),
    [
        (
            SERVICE_ADD_URL,
            [
                {
                    "method": "post",
                    "url": "https://127.0.0.1:3000/control/filtering/add_url",
                    "json": {
                        "whitelist": False,
                        "name": "Example",
                        "url": "https://example.com/1.txt",
                    },
                }
            ],
            {"name": "Example", "url": "https://example.com/1.txt"},
        ),
        (
            SERVICE_DISABLE_URL,
            [
                {
                    "method": "get",
                    "url": "https://127.0.0.1:3000/control/filtering/status",
                    "json": {
                        "filters": [
                            {
                                "name": "Example",
                                "url": "https://example.com/1.txt",
                            }
                        ],
                    },
                },
                {
                    "method": "post",
                    "url": "https://127.0.0.1:3000/control/filtering/set_url",
                    "json": {
                        "whitelist": False,
                        "url": "https://example.com/1.txt",
                    },
                },
            ],
            {"url": "https://example.com/1.txt"},
        ),
        (
            SERVICE_ENABLE_URL,
            [
                {
                    "method": "get",
                    "url": "https://127.0.0.1:3000/control/filtering/status",
                    "json": {
                        "filters": [
                            {
                                "name": "Example",
                                "url": "https://example.com/1.txt",
                            }
                        ],
                    },
                },
                {
                    "method": "post",
                    "url": "https://127.0.0.1:3000/control/filtering/set_url",
                    "json": {
                        "whitelist": False,
                        "url": "https://example.com/1.txt",
                    },
                },
            ],
            {"url": "https://example.com/1.txt"},
        ),
        (
            SERVICE_REFRESH,
            [
                {
                    "method": "post",
                    "url": "https://127.0.0.1:3000/control/filtering/refresh?force=false",
                    "json": {"whitelist": False},
                }
            ],
            {"force": False},
        ),
        (
            SERVICE_REMOVE_URL,
            [
                {
                    "method": "post",
                    "url": "https://127.0.0.1:3000/control/filtering/remove_url",
                    "json": {
                        "whitelist": False,
                        "url": "https://example.com/1.txt",
                    },
                }
            ],
            {"url": "https://example.com/1.txt"},
        ),
    ],
)
async def test_service(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    service: str,
    mocked_requests: list[dict],
    service_call_data: dict,
) -> None:
    """Test the adguard services be unregistered with unloading last entry."""
    for mocked_request in mocked_requests:
        aioclient_mock.request(
            mocked_request["method"],
            mocked_request["url"],
            json=mocked_request["json"],
            headers={"Content-Type": CONTENT_TYPE_JSON},
        )

    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, aioclient_mock)

    await hass.services.async_call(
        DOMAIN,
        service,
        service_call_data,
        blocking=True,
    )
