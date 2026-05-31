"""Tests for the Overkiz data update coordinator."""

from unittest.mock import Mock

from aiohttp import ClientConnectorError
from pyoverkiz.exceptions import (
    InvalidEventListenerIdException,
    MaintenanceException,
    ServiceUnavailableException,
    TooManyConcurrentRequestsException,
    TooManyRequestsException,
)
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import MockOverkizClient, SetupOverkizIntegration


@pytest.mark.parametrize(
    "exception",
    [
        TooManyConcurrentRequestsException("Too many concurrent requests"),
        TooManyRequestsException("Too many requests"),
        MaintenanceException("Server is down for maintenance"),
        ServiceUnavailableException("Server is unavailable"),
        InvalidEventListenerIdException("Invalid event listener id"),
        TimeoutError("Timed out"),
        ClientConnectorError(Mock(), Mock()),
    ],
    ids=[
        "too_many_concurrent_requests",
        "too_many_requests",
        "maintenance",
        "service_unavailable",
        "invalid_event_listener_id",
        "timeout",
        "client_connector_error",
    ],
)
async def test_transient_error_is_retried(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    exception: Exception,
) -> None:
    """Transient errors are translated into a retryable UpdateFailed."""
    config_entry = await setup_overkiz_integration()
    coordinator = config_entry.runtime_data.coordinator

    mock_client.fetch_events.side_effect = exception
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
