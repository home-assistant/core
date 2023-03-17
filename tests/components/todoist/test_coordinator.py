"""Tests for the TodoistCoordinator."""
import pytest

from homeassistant.components.todoist.calendar import _LOGGER, SCAN_INTERVAL
from homeassistant.components.todoist.coordinator import TodoistCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_async_update_data_success(api, hass: HomeAssistant, task) -> None:
    """Test data fetched successfully."""
    coordinator = TodoistCoordinator(hass, _LOGGER, SCAN_INTERVAL, api=api)
    data = await coordinator._async_update_data()
    assert data == [task]


async def test_async_update_data_exception(api, hass: HomeAssistant) -> None:
    """Test data fetch exception."""
    api.get_tasks.side_effect = Exception("API error")
    coordinator = TodoistCoordinator(hass, _LOGGER, SCAN_INTERVAL, api=api)
    with pytest.raises(UpdateFailed, match="Error communicating with API"):
        await coordinator._async_update_data()
