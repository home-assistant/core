"""Tests for the Overkiz data update coordinator."""

from pyoverkiz.exceptions import ServiceUnavailableException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import MockOverkizClient, SetupOverkizIntegration


async def test_service_unavailable_is_retried(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """A transient server error is translated into a retryable UpdateFailed."""
    config_entry = await setup_overkiz_integration()
    coordinator = config_entry.runtime_data.coordinator

    mock_client.fetch_events.side_effect = ServiceUnavailableException("Server error")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
