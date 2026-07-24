"""Tests for the AdGuard Home sensor entities."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.adguard.const import (
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_GET_URL_ENABLED,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


async def test_service_registration(
    hass: HomeAssistant,
) -> None:
    """Test the adguard services be registered."""
    services = hass.services.async_services_for_domain(DOMAIN)

    assert len(services) == 6
    assert SERVICE_ADD_URL in services
    assert SERVICE_DISABLE_URL in services
    assert SERVICE_ENABLE_URL in services
    assert SERVICE_REFRESH in services
    assert SERVICE_REMOVE_URL in services
    assert SERVICE_GET_URL_ENABLED in services


@pytest.mark.parametrize(
    ("service", "service_call_data", "call_assertion"),
    [
        (
            SERVICE_ADD_URL,
            {"name": "Example", "url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.add_url.assert_called_once(),
        ),
        (
            SERVICE_DISABLE_URL,
            {"url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.disable_url.assert_called_once(),
        ),
        (
            SERVICE_ENABLE_URL,
            {"url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.enable_url.assert_called_once(),
        ),
        (
            SERVICE_REFRESH,
            {"force": False},
            lambda mock: mock.filtering.refresh.assert_called_once(),
        ),
        (
            SERVICE_REMOVE_URL,
            {"url": "https://example.com/1.txt"},
            lambda mock: mock.filtering.remove_url.assert_called_once(),
        ),
    ],
)
async def test_service(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    service: str,
    service_call_data: dict,
    call_assertion: Callable[[AsyncMock], Any],
) -> None:
    """Test the adguard services be unregistered with unloading last entry."""
    await hass.services.async_call(
        DOMAIN,
        service,
        service_call_data,
        blocking=True,
    )

    call_assertion(mock_adguard)


@pytest.mark.parametrize(
    ("call_data", "adguard_response", "expected_service_response_data"),
    [
        (
            {"url": "https://example.com/1.txt"},
            True,
            {"enabled": True},
        ),
        (
            {"url": "https://example.com/1.txt"},
            False,
            {"enabled": False},
        ),
    ],
)
async def test_url_enabled_response(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_device_id: str,
    call_data: dict,
    adguard_response: bool,
    expected_service_response_data: Any,
) -> None:
    """Test the adguard url_enabled service response."""
    service_call_data = {"device_id": mock_device_id} | call_data
    mock_adguard.filtering.url_enabled.return_value = adguard_response

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_URL_ENABLED,
        service_call_data,
        blocking=True,
        return_response=True,
    )

    assert result == expected_service_response_data


async def test_url_enabled_invalid_device_id(
    hass: HomeAssistant,
) -> None:
    """Test the adguard url_enabled service response with invalid device_id."""
    service_call_data = {"device_id": "invalid-id", "url": "https://example.com/1.txt"}

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_URL_ENABLED,
            service_call_data,
            blocking=True,
            return_response=True,
        )

    assert excinfo.value.translation_key == "invalid_device_id"


async def test_url_enabled_config_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_id: str,
) -> None:
    """Test the adguard url_enabled service with unloaded config entry."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    service_call_data = {
        "device_id": mock_device_id,
        "url": "https://example.com/1.txt",
    }

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_URL_ENABLED,
            service_call_data,
            blocking=True,
            return_response=True,
        )

    assert excinfo.value.translation_key == "config_entry_not_loaded"
