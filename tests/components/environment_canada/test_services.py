"""Tests for the Environment Canada services."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.environment_canada.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration

SERVICE_GET_ALERTS = "get_alerts"


async def test_get_alerts(
    hass: HomeAssistant, snapshot: SnapshotAssertion, ec_data: dict[str, Any]
) -> None:
    """Test the get_alerts service returns active alerts."""
    config_entry = await init_integration(hass, ec_data)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ALERTS,
        {"config_entry_id": config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_get_alerts_not_connected(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test get_alerts raises when weather data is not connected."""
    config_entry = await init_integration(hass, ec_data)
    config_entry.runtime_data.weather_coordinator.ec_data = None

    with pytest.raises(HomeAssistantError, match="not connected"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_ALERTS,
            {"config_entry_id": config_entry.entry_id},
            blocking=True,
            return_response=True,
        )
