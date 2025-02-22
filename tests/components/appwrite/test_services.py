"""Test the Appwrite services."""

from hashlib import md5
from unittest.mock import Mock

from appwrite.client import AppwriteException
import pytest

from homeassistant.components.appwrite.const import (
    DOMAIN,
    FUNCTION_BODY,
    FUNCTION_HEADERS,
    FUNCTION_PATH,
)
from homeassistant.components.appwrite.services import AppwriteServices
from homeassistant.core import HomeAssistant


async def test_build_service_name(
    appwrite_services: AppwriteServices, mock_appwrite_client
) -> None:
    """Test service name generation."""
    base_service_id = md5(
        f"{mock_appwrite_client.endpoint}_{mock_appwrite_client.project_id}".encode()
    ).hexdigest()
    expected_name = f"{base_service_id}_function_id"

    service_name = appwrite_services._AppwriteServices__build_service_name(
        "function_id"
    )
    assert service_name == expected_name


async def test_service_registration(
    hass: HomeAssistant, appwrite_services: AppwriteServices
) -> None:
    """Test service registration."""
    service_name = appwrite_services._AppwriteServices__build_service_name(
        "function_id"
    )
    assert hass.services.has_service(DOMAIN, service_name)


async def test_execute_function_service_with_body(
    hass: HomeAssistant,
    appwrite_services: AppwriteServices,
    mock_appwrite_client: Mock,
) -> None:
    """Test successful service function execution with body."""
    expected_response = {"status": "completed", "response": "test response"}
    mock_appwrite_client.async_execute_function.return_value = expected_response

    service_name = appwrite_services._AppwriteServices__build_service_name(
        "function_id"
    )
    service_data = {
        FUNCTION_BODY: "test-body",
    }

    response = await hass.services.async_call(
        DOMAIN,
        service_name,
        service_data,
        blocking=True,
        return_response=True,
    )

    mock_appwrite_client.async_execute_function.assert_called_once_with(
        "function-id", "test-body", None, None, None, False, "GET"
    )
    assert response == expected_response


async def test_execute_function_service_without_body(
    hass: HomeAssistant,
    appwrite_services: AppwriteServices,
    mock_appwrite_client: Mock,
) -> None:
    """Test successful service function execution without body."""
    expected_response = {"status": "completed", "response": "test response"}
    mock_appwrite_client.async_execute_function.return_value = expected_response

    service_name = appwrite_services._AppwriteServices__build_service_name(
        "function_id"
    )
    service_data = {}

    response = await hass.services.async_call(
        DOMAIN,
        service_name,
        service_data,
        blocking=True,
        return_response=True,
    )

    mock_appwrite_client.async_execute_function.assert_called_once_with(
        "function-id", None, None, None, None, False, "GET"
    )
    assert response == expected_response


async def test_execute_function_service_with_path(
    hass: HomeAssistant,
    appwrite_services: AppwriteServices,
    mock_appwrite_client: Mock,
) -> None:
    """Test successful service function execution without body."""
    expected_response = {"status": "completed", "response": "test response"}
    mock_appwrite_client.async_execute_function.return_value = expected_response

    service_name = appwrite_services._AppwriteServices__build_service_name(
        "function_id"
    )
    service_data = {FUNCTION_PATH: "?query=param"}

    response = await hass.services.async_call(
        DOMAIN,
        service_name,
        service_data,
        blocking=True,
        return_response=True,
    )

    mock_appwrite_client.async_execute_function.assert_called_once_with(
        "function-id", None, "?query=param", None, None, False, "GET"
    )
    assert response == expected_response


async def test_execute_function_service_with_headers(
    hass: HomeAssistant,
    appwrite_services: AppwriteServices,
    mock_appwrite_client: Mock,
) -> None:
    """Test successful service function execution without body."""
    expected_response = {"status": "completed", "response": "test response"}
    mock_appwrite_client.async_execute_function.return_value = expected_response

    service_name = appwrite_services._AppwriteServices__build_service_name(
        "function_id"
    )
    service_data = {FUNCTION_HEADERS: {"header": "value"}}

    response = await hass.services.async_call(
        DOMAIN,
        service_name,
        service_data,
        blocking=True,
        return_response=True,
    )

    mock_appwrite_client.async_execute_function.assert_called_once_with(
        "function-id", None, None, {"header": "value"}, None, False, "GET"
    )
    assert response == expected_response


async def test_execute_function_service_error(
    hass: HomeAssistant,
    appwrite_services: AppwriteServices,
    mock_appwrite_client: Mock,
) -> None:
    """Test function execution service with error."""
    mock_appwrite_client.async_execute_function.side_effect = AppwriteException(
        "Test error"
    )

    service_name = appwrite_services._AppwriteServices__build_service_name(
        "function_id"
    )
    service_data = {
        FUNCTION_BODY: "test-body",
    }

    with pytest.raises(AppwriteException) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            service_data,
            blocking=True,
            return_response=True,
        )

    assert str(exc_info.value) == "Test error"
    mock_appwrite_client.async_execute_function.assert_called_once_with(
        "function-id", "test-body", None, None, None, False, "GET"
    )
