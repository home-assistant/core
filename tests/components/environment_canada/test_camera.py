"""Test Environment Canada camera."""

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.environment_canada.camera import SERVICE_SET_RADAR_TYPE
from homeassistant.components.environment_canada.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_camera_entity(hass: HomeAssistant, ec_data: dict[str, Any]) -> None:
    """Test camera entity setup."""
    await init_integration(hass, ec_data)

    state = hass.states.get("camera.home_radar")
    # Camera is disabled by default, so state should be None
    assert state is None


async def test_set_radar_type_rain(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test setting radar type to rain."""
    config_entry = await init_integration(hass, ec_data)
    radar_coordinator = config_entry.runtime_data.radar_coordinator
    radar_mock = radar_coordinator.ec_data

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RADAR_TYPE,
        {"entity_id": "camera.home_radar", "radar_type": "Rain"},
        blocking=True,
    )

    assert radar_mock.layer == "rain"
    radar_mock.update.assert_called()


async def test_set_radar_type_snow(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test setting radar type to snow."""
    config_entry = await init_integration(hass, ec_data)
    radar_coordinator = config_entry.runtime_data.radar_coordinator
    radar_mock = radar_coordinator.ec_data

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RADAR_TYPE,
        {"entity_id": "camera.home_radar", "radar_type": "Snow"},
        blocking=True,
    )

    assert radar_mock.layer == "snow"
    radar_mock.update.assert_called()


async def test_set_radar_type_precip_type(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test setting radar type to precip type."""
    config_entry = await init_integration(hass, ec_data)
    radar_coordinator = config_entry.runtime_data.radar_coordinator
    radar_mock = radar_coordinator.ec_data

    # First set to something else
    radar_mock.layer = "rain"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RADAR_TYPE,
        {"entity_id": "camera.home_radar", "radar_type": "Precip Type"},
        blocking=True,
    )

    assert radar_mock.layer == "precip_type"
    radar_mock.update.assert_called()


@pytest.mark.parametrize(
    ("month", "expected_layer"),
    [
        (1, "snow"),  # January - winter
        (2, "snow"),  # February - winter
        (3, "snow"),  # March - winter
        (4, "rain"),  # April - spring/summer
        (5, "rain"),  # May - spring/summer
        (6, "rain"),  # June - summer
        (7, "rain"),  # July - summer
        (8, "rain"),  # August - summer
        (9, "rain"),  # September - summer
        (10, "rain"),  # October - fall
        (11, "snow"),  # November - winter
        (12, "snow"),  # December - winter
    ],
)
async def test_set_radar_type_auto(
    hass: HomeAssistant,
    ec_data: dict[str, Any],
    month: int,
    expected_layer: str,
) -> None:
    """Test auto radar type selects rain or snow based on month."""
    config_entry = await init_integration(hass, ec_data)
    radar_coordinator = config_entry.runtime_data.radar_coordinator
    radar_mock = radar_coordinator.ec_data

    with patch.object(date, "today", return_value=date(2024, month, 15)):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_RADAR_TYPE,
            {"entity_id": "camera.home_radar", "radar_type": "Auto"},
            blocking=True,
        )

    assert radar_mock.layer == expected_layer
    radar_mock.update.assert_called()


async def test_set_radar_type_clears_cache(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test that setting radar type clears the cache."""
    config_entry = await init_integration(hass, ec_data)
    radar_coordinator = config_entry.runtime_data.radar_coordinator
    radar_mock = radar_coordinator.ec_data

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RADAR_TYPE,
        {"entity_id": "camera.home_radar", "radar_type": "Rain"},
        blocking=True,
    )

    # Verify clear_cache was called on the radar object
    radar_mock.clear_cache.assert_called_once()
