"""Test that DataUpdateCoordinator recovers from DNS failures."""

from datetime import timedelta
import logging

from aiohttp import ClientError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MockCoordinator(DataUpdateCoordinator[dict]):
    """Test coordinator that simulates API calls."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="test",
            update_interval=timedelta(seconds=60),
            config_entry=None,
            update_method=self._async_update_data,
        )
        self._test_data: dict | None = {"value": 1}
        self._should_fail = False

    async def _async_update_data(self) -> dict:
        """Fetch data."""
        if self._should_fail:
            raise ClientError("Simulated DNS failure")
        assert self._test_data is not None
        return self._test_data


@pytest.fixture
def coordinator(hass: HomeAssistant) -> MockCoordinator:
    """Create a mock coordinator."""
    return MockCoordinator(hass)


async def test_session_survives_failed_update(
    hass: HomeAssistant, coordinator: MockCoordinator
) -> None:
    """Test session stays open after update failure."""
    session = async_get_clientsession(hass)

    coordinator._should_fail = True
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert not session.closed


async def test_coordinator_recovers_after_failure(
    hass: HomeAssistant, coordinator: MockCoordinator
) -> None:
    """Test coordinator succeeds after a failure."""
    coordinator._should_fail = True
    await coordinator.async_refresh()
    assert not coordinator.last_update_success

    coordinator._should_fail = False
    coordinator._test_data = {"value": 2}
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data == {"value": 2}


async def test_multiple_failures_then_recovery(
    hass: HomeAssistant, coordinator: MockCoordinator
) -> None:
    """Test multiple failures followed by recovery."""
    coordinator._should_fail = True
    for _ in range(3):
        await coordinator.async_refresh()
        assert not coordinator.last_update_success

    coordinator._should_fail = False
    coordinator._test_data = {"value": "recovered"}
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data == {"value": "recovered"}


async def test_connector_has_clear_dns_cache(
    hass: HomeAssistant,
) -> None:
    """Test that the shared connector has clear_dns_cache method."""
    session = async_get_clientsession(hass)
    assert hasattr(session.connector, "clear_dns_cache")
    assert callable(session.connector.clear_dns_cache)

    # Should not raise when called
    session.connector.clear_dns_cache()


async def test_connector_clear_dns_cache_works(
    hass: HomeAssistant,
) -> None:
    """Test that clear_dns_cache actually runs without error."""
    session = async_get_clientsession(hass)

    # Call it multiple times — should never raise
    for _ in range(3):
        session.connector.clear_dns_cache()

    assert not session.closed
