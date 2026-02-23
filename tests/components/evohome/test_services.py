"""The tests for the native services of Evohome."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from evohomeasync2 import EvohomeClient
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.evohome.const import (
    ATTR_DURATION,
    ATTR_PERIOD,
    ATTR_SETPOINT,
    DOMAIN,
    EvoService,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize("install", ["default"])
async def test_service_refresh_system(
    hass: HomeAssistant,
    evohome: EvohomeClient,
) -> None:
    """Test Evohome's refresh_system service (for all temperature control systems)."""

    # EvoService.REFRESH_SYSTEM
    with patch("evohomeasync2.location.Location.update") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.REFRESH_SYSTEM,
            {},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


@pytest.mark.parametrize("install", ["default"])
async def test_service_reset_system(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test Evohome's reset_system service (for a temperature control system)."""

    # EvoService.RESET_SYSTEM (if SZ_AUTO_WITH_RESET in modes)
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.RESET_SYSTEM,
            {},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with("AutoWithReset", until=None)


@pytest.mark.parametrize("install", ["default"])
async def test_ctl_set_system_mode(
    hass: HomeAssistant,
    ctl_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Evohome's set_system_mode service (for a temperature control system)."""

    # EvoService.SET_SYSTEM_MODE: Auto
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Auto",
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with("Auto", until=None)

    freezer.move_to("2024-07-10T12:00:00+00:00")

    # EvoService.SET_SYSTEM_MODE: AutoWithEco, hours=12
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "AutoWithEco",
                ATTR_DURATION: {"hours": 12},
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(
            "AutoWithEco", until=datetime(2024, 7, 11, 0, 0, tzinfo=UTC)
        )

    # EvoService.SET_SYSTEM_MODE: Away, days=7
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Away",
                ATTR_PERIOD: {"days": 7},
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(
            "Away", until=datetime(2024, 7, 16, 23, 0, tzinfo=UTC)
        )


@pytest.mark.parametrize("install", ["default"])
async def test_zone_clear_zone_override(
    hass: HomeAssistant,
    zone_id: str,
) -> None:
    """Test Evohome's clear_zone_override service (for a heating zone)."""

    # EvoZoneMode.FOLLOW_SCHEDULE
    with patch("evohomeasync2.zone.Zone.reset") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.RESET_ZONE_OVERRIDE,
            {
                ATTR_ENTITY_ID: zone_id,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


@pytest.mark.parametrize("install", ["default"])
async def test_zone_set_zone_override(
    hass: HomeAssistant,
    zone_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Evohome's set_zone_override service (for a heating zone)."""

    freezer.move_to("2024-07-10T12:00:00+00:00")

    # EvoZoneMode.PERMANENT_OVERRIDE
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_ZONE_OVERRIDE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_SETPOINT: 19.5,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(19.5, until=None)

    # EvoZoneMode.TEMPORARY_OVERRIDE
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_ZONE_OVERRIDE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_SETPOINT: 19.5,
                ATTR_DURATION: {"minutes": 135},
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(
            19.5, until=datetime(2024, 7, 10, 14, 15, tzinfo=UTC)
        )
