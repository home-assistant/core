"""Tests for Ghost sensors."""

from unittest.mock import AsyncMock

from aioghost.exceptions import GhostError

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import NEWSLETTERS_DATA


async def test_newsletter_sensor_added_on_update(
    hass: HomeAssistant,
    mock_ghost_api: AsyncMock,
    mock_config_entry,
) -> None:
    """Test newsletter sensors are added after updates."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_ghost_monthly_subscribers") is None

    mock_ghost_api.get_newsletters.return_value = [
        *NEWSLETTERS_DATA,
        {
            "id": "nl3",
            "name": "Monthly",
            "status": "active",
            "count": {"members": 300},
        },
    ]

    await mock_config_entry.runtime_data.coordinator.async_request_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_ghost_monthly_subscribers")
    assert state is not None
    assert state.state == "300"


async def test_revenue_sensors_not_created_without_stripe(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test MRR/ARR sensors are not created when Stripe is not linked."""
    # Return empty MRR/ARR data (no Stripe linked)
    mock_ghost_api.get_mrr.return_value = {}
    mock_ghost_api.get_arr.return_value = {}

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_ghost_mrr") is None
    assert hass.states.get("sensor.test_ghost_arr") is None


async def test_newsletter_sensor_not_found(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test newsletter sensor when newsletter is removed."""
    await setup_integration(hass, mock_config_entry)

    # Verify newsletter sensor exists
    state = hass.states.get("sensor.test_ghost_weekly_subscribers")
    assert state is not None
    assert state.state == "800"

    # Now return empty newsletters list
    mock_ghost_api.get_newsletters.return_value = []

    await mock_config_entry.runtime_data.coordinator.async_request_refresh()
    await hass.async_block_till_done()

    # Sensor should now be unavailable (newsletter not found)
    state = hass.states.get("sensor.test_ghost_weekly_subscribers")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_entities_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_ghost_api: AsyncMock,
    mock_config_entry,
) -> None:
    """Test entities become unavailable on update failure."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.test_ghost_total_members")
    assert state is not None
    assert state.state == "1000"

    mock_ghost_api.get_site.side_effect = GhostError("Update failed")

    await mock_config_entry.runtime_data.coordinator.async_request_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_ghost_total_members")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
