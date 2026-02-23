"""Tests for ViCare DHW circulation boost service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.vicare.const import (
    DOMAIN,
    SERVICE_ACTIVATE_DHW_CIRCULATION_BOOST,
)
from homeassistant.core import HomeAssistant

from tests.common import async_capture_events


def _schedule_fixture(active: bool = True) -> dict[str, object]:
    """Return a minimal schedule payload."""
    return {
        "active": active,
        "default_mode": "off",
        "mon": [],
        "tue": [],
        "wed": [],
        "thu": [],
        "fri": [],
        "sat": [],
        "sun": [],
    }


async def test_boost_service_fires_lifecycle_events(
    hass: HomeAssistant,
    mock_vicare_gas_boiler,
) -> None:
    """Test that the boost service emits lifecycle events."""
    events = async_capture_events(hass, "vicare_dhw_circulation_boost")
    device = mock_vicare_gas_boiler.runtime_data.devices[0].api

    with (
        patch(
            "homeassistant.components.vicare.circulation.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch.object(
            device,
            "getDomesticHotWaterStorageTemperature",
            side_effect=[40.0, 46.0],
        ),
        patch.object(
            device,
            "getDomesticHotWaterCirculationSchedule",
            return_value=_schedule_fixture(),
        ),
        patch.object(
            device,
            "getDomesticHotWaterSchedule",
            return_value=_schedule_fixture(),
        ),
        patch.object(device, "setDomesticHotWaterCirculationSchedule"),
        patch.object(device, "setProperty"),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_DHW_CIRCULATION_BOOST,
            {
                "duration_minutes": 30,
                "min_boost_temperature": 45.0,
                "target_setpoint": 55.0,
                "heat_timeout_minutes": 10,
                "warm_water_delay_minutes": 1,
            },
            blocking=True,
        )

    await hass.async_block_till_done()

    stages = [event.data["stage"] for event in events]
    assert stages == [
        "boost_initiated",
        "water_heating",
        "water_circulation_started",
        "warm_water_available",
    ]
    assert all(event.data["min_boost_temperature"] == 45.0 for event in events)


async def test_boost_service_uses_legacy_min_storage_alias(
    hass: HomeAssistant,
    mock_vicare_gas_boiler,
) -> None:
    """Test that legacy min_storage_temperature still controls heating threshold."""
    events = async_capture_events(hass, "vicare_dhw_circulation_boost")
    device = mock_vicare_gas_boiler.runtime_data.devices[0].api

    with (
        patch(
            "homeassistant.components.vicare.circulation.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch.object(
            device,
            "getDomesticHotWaterStorageTemperature",
            return_value=44.0,
        ),
        patch.object(
            device,
            "getDomesticHotWaterCirculationSchedule",
            return_value=_schedule_fixture(),
        ),
        patch.object(device, "setDomesticHotWaterCirculationSchedule"),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_DHW_CIRCULATION_BOOST,
            {
                "duration_minutes": 30,
                "min_storage_temperature": 42.0,
                "heat_timeout_minutes": 10,
                "warm_water_delay_minutes": 1,
            },
            blocking=True,
        )

    await hass.async_block_till_done()

    stages = [event.data["stage"] for event in events]
    assert "water_heating" not in stages
    assert events[0].data["min_boost_temperature"] == 42.0
