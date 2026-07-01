"""Tests for the Gatus DataUpdateCoordinator."""

import json
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from gatus_api.client import GatusClientError

from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import async_fire_time_changed, load_fixture


async def test_coordinator_successful_update(
    hass: HomeAssistant, mock_gatus_client: AsyncMock
) -> None:
    """Test a pristine successful data refresh cycle and URL sanitization."""
    mock_data = [{"key": "endpoint_1", "is_up": True}]
    config_entry = await setup_integration(hass, mock_gatus_client, mock_data)
    coordinator: GatusDataUpdateCoordinator = config_entry.runtime_data

    assert coordinator.url == "http://gatus.local:80"

    assert coordinator.last_update_success is True
    assert isinstance(coordinator.data, list)
    assert coordinator.data[0]["key"] == "endpoint_1"


async def test_coordinator_client_error(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a library exception cleanly marks a runtime update as failed."""

    fixture_data = await hass.async_add_executor_job(
        load_fixture, "gatus/statuses_success.json"
    )
    mock_data = json.loads(fixture_data)

    config_entry = await setup_integration(hass, mock_gatus_client, mock_data)
    coordinator: GatusDataUpdateCoordinator = config_entry.runtime_data

    assert coordinator.last_update_success is True

    mock_gatus_client.get_endpoints_statuses.side_effect = GatusClientError(
        "Error communicating with Gatus API: status code 500"
    )

    freezer.tick(coordinator.update_interval)

    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
