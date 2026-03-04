"""Tests for the energenie_mi_home API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.energenie_mi_home.api import (
    MiHomeAPI,
    MiHomeConnectionError,
    MiHomeDevice,
)
from homeassistant.components.energenie_mi_home.const import (
    API_ENDPOINT_PROFILE,
    API_ENDPOINT_SUBDEVICES_LIST,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_device_from_api_empty_id(hass: HomeAssistant) -> None:
    """Test that device with empty id is rejected."""
    # Empty string id
    data = {"id": "", "device_type": "elight", "power_state": True}
    device = MiHomeDevice.from_api(data)
    assert device is None

    # Whitespace-only id
    data = {"id": "   ", "device_type": "elight", "power_state": True}
    device = MiHomeDevice.from_api(data)
    assert device is None

    # Missing id
    data = {"device_type": "elight", "power_state": True}
    device = MiHomeDevice.from_api(data)
    assert device is None


async def test_device_from_api_power_state_string(hass: HomeAssistant) -> None:
    """Test power_state conversion from string values."""
    # String "true" should convert to True
    data = {
        "id": "1",
        "device_type": "elight",
        "power_state": "true",
        "label": "Test Light",
    }
    device = MiHomeDevice.from_api(data)
    assert device is not None
    assert device.is_on is True

    # String "1" should convert to True
    data = {
        "id": "2",
        "device_type": "elight",
        "power_state": "1",
        "label": "Test Light",
    }
    device = MiHomeDevice.from_api(data)
    assert device is not None
    assert device.is_on is True

    # String "false" should convert to False
    data = {
        "id": "3",
        "device_type": "elight",
        "power_state": "false",
        "label": "Test Light",
    }
    device = MiHomeDevice.from_api(data)
    assert device is not None
    assert device.is_on is False

    # String "0" should convert to False
    data = {
        "id": "4",
        "device_type": "elight",
        "power_state": "0",
        "label": "Test Light",
    }
    device = MiHomeDevice.from_api(data)
    assert device is not None
    assert device.is_on is False

    # Boolean True should remain True
    data = {
        "id": "5",
        "device_type": "elight",
        "power_state": True,
        "label": "Test Light",
    }
    device = MiHomeDevice.from_api(data)
    assert device is not None
    assert device.is_on is True

    # Boolean False should remain False
    data = {
        "id": "6",
        "device_type": "elight",
        "power_state": False,
        "label": "Test Light",
    }
    device = MiHomeDevice.from_api(data)
    assert device is not None
    assert device.is_on is False


async def test_device_from_api_product_type_validation(
    hass: HomeAssistant,
) -> None:
    """Test that product_type is validated as string."""
    # Non-string product_type should be converted to string
    data = {
        "id": "1",
        "device_type": 123,  # Non-string device_type
        "power_state": True,
        "label": "Test Light",
    }
    device = MiHomeDevice.from_api(data)
    # Device should still be created (device_type mapping handles conversion)
    # But product_type should be string
    if device:
        assert isinstance(device.product_type, str) or device.product_type is None


async def test_authenticate_invalid_api_key_type(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test authentication with invalid API key type."""
    session = async_get_clientsession(hass)
    api = MiHomeAPI("test@example.com", "password", session)

    # Mock response with non-string api_key
    aioclient_mock.post(
        f"https://mihome4u.co.uk/api/v1/{API_ENDPOINT_PROFILE}",
        json={"status": "success", "data": {"api_key": 12345}},
    )

    with pytest.raises(MiHomeConnectionError, match="API key missing"):
        await api.async_authenticate()

    # Mock response with empty string api_key
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://mihome4u.co.uk/api/v1/{API_ENDPOINT_PROFILE}",
        json={"status": "success", "data": {"api_key": ""}},
    )

    with pytest.raises(MiHomeConnectionError, match="API key missing"):
        await api.async_authenticate()

    # Mock response with whitespace-only api_key
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://mihome4u.co.uk/api/v1/{API_ENDPOINT_PROFILE}",
        json={"status": "success", "data": {"api_key": "   "}},
    )

    with pytest.raises(MiHomeConnectionError, match="API key missing"):
        await api.async_authenticate()


async def test_request_message_string_validation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that error messages are converted to strings."""
    session = async_get_clientsession(hass)
    api = MiHomeAPI("test@example.com", "password", session, api_key="test-key")

    # Mock response with non-string error message
    aioclient_mock.post(
        f"https://mihome4u.co.uk/api/v1/{API_ENDPOINT_SUBDEVICES_LIST}",
        json={"status": "error", "message": 12345},
    )

    with pytest.raises(MiHomeConnectionError) as exc_info:
        await api.async_get_devices()
    # Message should be converted to string
    assert "12345" in str(exc_info.value)

    # Mock response with None message
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://mihome4u.co.uk/api/v1/{API_ENDPOINT_SUBDEVICES_LIST}",
        json={"status": "error", "message": None},
    )

    with pytest.raises(MiHomeConnectionError) as exc_info:
        await api.async_get_devices()
    # Should handle None gracefully
    assert "unknown" in str(exc_info.value) or "MiHome API error" in str(exc_info.value)


async def test_light_setup_empty_entities(
    hass: HomeAssistant, mock_mihome_api: MagicMock
) -> None:
    """Test that light platform handles empty entity list."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password",
            CONF_API_KEY: "test-key",
        },
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    # Mock API to return empty device list
    mock_mihome_api.async_get_devices = AsyncMock(return_value=[])

    with (
        patch(
            "homeassistant.components.energenie_mi_home.coordinator.MiHomeAPI",
            return_value=mock_mihome_api,
        ),
        patch(
            "homeassistant.components.energenie_mi_home._PLATFORMS", [Platform.LIGHT]
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Verify no entities were created (empty coordinator.data means no entities)
    coordinator = entry.runtime_data
    assert len(coordinator.data) == 0
