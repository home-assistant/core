"""The tests for the native services of Evohome."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.evohome.const import (
    ATTR_DURATION,
    ATTR_PERIOD,
    ATTR_SETPOINT,
    DOMAIN,
    EvoService,
)
from homeassistant.components.evohome.water_heater import EvoDHW
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, ATTR_STATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import DATA_DOMAIN_PLATFORM_ENTITIES

from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
async def test_refresh_system(hass: HomeAssistant) -> None:
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


@pytest.mark.parametrize("install", TEST_INSTALLS)  # some don't support AutoWithReset
@pytest.mark.usefixtures("evohome")
async def test_reset_system(
    hass: HomeAssistant,
) -> None:
    """Test Evohome's reset_system service (for a temperature control system)."""

    # EvoService.RESET_SYSTEM
    with patch("evohomeasync2.control_system.ControlSystem.reset") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.RESET_SYSTEM,
            {},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("ctl_id")
async def test_set_system_mode(
    hass: HomeAssistant,
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
async def test_clear_zone_override(
    hass: HomeAssistant,
    zone_id: str,
) -> None:
    """Test Evohome's clear_zone_override service (for a heating zone)."""

    # EvoZoneMode.FOLLOW_SCHEDULE
    with patch("evohomeasync2.zone.Zone.reset") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.CLEAR_ZONE_OVERRIDE,
            {},
            target={ATTR_ENTITY_ID: zone_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


@pytest.mark.parametrize("install", ["default"])
async def test_clear_zone_override_legacy(
    hass: HomeAssistant,
    zone_id: str,
) -> None:
    """Test Evohome's clear_zone_override service with the legacy entity_id."""

    # EvoZoneMode.FOLLOW_SCHEDULE
    with patch("evohomeasync2.zone.Zone.reset") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.CLEAR_ZONE_OVERRIDE,
            {
                ATTR_ENTITY_ID: zone_id,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


@pytest.mark.parametrize("install", ["default"])
async def test_set_zone_override(
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
                ATTR_SETPOINT: 19.5,
            },
            target={ATTR_ENTITY_ID: zone_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(19.5, until=None)

    # EvoZoneMode.TEMPORARY_OVERRIDE
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_ZONE_OVERRIDE,
            {
                ATTR_SETPOINT: 19.5,
                ATTR_DURATION: {"minutes": 135},
            },
            target={ATTR_ENTITY_ID: zone_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(
            19.5, until=datetime(2024, 7, 10, 14, 15, tzinfo=UTC)
        )


@pytest.mark.parametrize("install", ["default"])
async def test_set_zone_override_legacy(
    hass: HomeAssistant,
    zone_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Evohome's set_zone_override service with the legacy entity_id."""

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


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (EvoService.CLEAR_ZONE_OVERRIDE, {}),
        (EvoService.SET_ZONE_OVERRIDE, {ATTR_SETPOINT: 19.5}),
    ],
)
async def test_zone_services_with_ctl_id(
    hass: HomeAssistant,
    ctl_id: str,
    service: EvoService,
    service_data: dict[str, Any],
) -> None:
    """Test calling zone-only services with a non-zone entity_id fail."""

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service,
            service_data,
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

    assert exc_info.value.translation_key == "zone_only_service"
    assert exc_info.value.translation_placeholders == {"service": service}


_SET_SYSTEM_MODE_VALIDATOR_PARAMS = [
    (
        {ATTR_MODE: "NotARealMode"},
        "mode_not_supported",
    ),
    (
        {ATTR_MODE: "Auto", ATTR_DURATION: {"hours": 1}},
        "mode_cant_be_temporary",
    ),
    (
        {ATTR_MODE: "AutoWithEco", ATTR_PERIOD: {"days": 1}},
        "mode_cant_have_period",
    ),
    (
        {ATTR_MODE: "DayOff", ATTR_DURATION: {"hours": 1}},
        "mode_cant_have_duration",
    ),
]


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
@pytest.mark.parametrize(
    ("service_data", "expected_translation_key"),
    _SET_SYSTEM_MODE_VALIDATOR_PARAMS,
    ids=[k for _, k in _SET_SYSTEM_MODE_VALIDATOR_PARAMS],
)
async def test_set_system_mode_validator(
    hass: HomeAssistant,
    service_data: dict[str, Any],
    expected_translation_key: str,
) -> None:
    """Test ServiceValidationError for all controller system mode validation cases."""

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            service_data,
            target={},
            blocking=True,
        )

    assert exc_info.value.translation_key == expected_translation_key
    assert exc_info.value.translation_placeholders == {
        ATTR_MODE: service_data[ATTR_MODE]
    }


@pytest.mark.parametrize("install", ["default"])
async def test_set_dhw_override(
    hass: HomeAssistant,
    dhw_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Evohome's set_dhw_override service (for a DHW zone)."""

    freezer.move_to("2024-07-10T12:00:00+00:00")

    # EvoZoneMode.PERMANENT_OVERRIDE (off)
    with patch("evohomeasync2.hotwater.HotWater.set_off") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_DHW_OVERRIDE,
            {
                ATTR_STATE: False,
            },
            target={ATTR_ENTITY_ID: dhw_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(until=None)

    # EvoZoneMode.TEMPORARY_OVERRIDE (on)
    with patch("evohomeasync2.hotwater.HotWater.set_on") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_DHW_OVERRIDE,
            {
                ATTR_STATE: True,
                ATTR_DURATION: {"minutes": 135},
            },
            target={ATTR_ENTITY_ID: dhw_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(
            until=datetime(2024, 7, 10, 14, 15, tzinfo=UTC)
        )


@pytest.mark.parametrize("install", ["default"])
async def test_set_dhw_override_advance(
    hass: HomeAssistant,
    dhw_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Evohome's set_dhw_override service with duration=0.

    The override is temporary until the next schedule change.
    """

    freezer.move_to("2024-05-10T12:15:00+00:00")
    expected_until = datetime(2024, 5, 10, 15, 30, tzinfo=UTC)

    # Simulate the schedule not yet having been fetched (e.g. HOMEASSISTANT_START)
    entities = hass.data[DATA_DOMAIN_PLATFORM_ENTITIES].get(
        (WATER_HEATER_DOMAIN, DOMAIN), {}
    )

    dhw_entity: EvoDHW = entities[dhw_id]  # type: ignore[assignment]
    dhw_entity._schedule = None
    dhw_entity._setpoints = {}

    # EvoZoneMode.TEMPORARY_OVERRIDE with duration 0 (i.e. until next schedule change)
    with patch("evohomeasync2.hotwater.HotWater.set_on") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_DHW_OVERRIDE,
            {
                ATTR_STATE: True,
                ATTR_DURATION: {"minutes": 0},
            },
            target={ATTR_ENTITY_ID: dhw_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(until=expected_until)

    assert dhw_entity.setpoints["next_sp_from"] == expected_until
