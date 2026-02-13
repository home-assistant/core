"""The tests for the native services of Evohome."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from evohomeasync2 import EvohomeClient
from freezegun.api import FrozenDateTimeFactory
import pytest
from voluptuous.error import MultipleInvalid

from homeassistant.components.evohome.const import (
    ATTR_DURATION,
    ATTR_PERIOD,
    ATTR_SETPOINT,
    DOMAIN,
    EvoService,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, CONF_TARGET
from homeassistant.core import HomeAssistant
import homeassistant.exceptions
from homeassistant.helpers import issue_registry as ir

# Domain-level service call tests (controller/TCS)


@pytest.mark.parametrize("install", ["default"])
async def test_service_refresh_system(
    hass: HomeAssistant,
    evohome: EvohomeClient,
) -> None:
    """Test domain-level refresh_system call."""

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
    """Test domain-level reset_system call."""

    with patch("evohomeasync2.control_system.ControlSystem.reset") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.RESET_SYSTEM,
            {},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode(
    hass: HomeAssistant,
    ctl_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test domain-level set_system_mode call."""

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
async def test_set_system_mode_both_duration_and_period(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test set_system_mode rejects both duration and period."""

    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Away",
                ATTR_DURATION: {"hours": 12},
                ATTR_PERIOD: {"days": 7},
            },
            blocking=True,
        )


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_invalid_mode(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test set_system_mode rejects a mode not in the allowed system modes."""

    # "Off" is not in the default fixture's allowed system modes
    with pytest.raises(homeassistant.exceptions.ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {ATTR_MODE: "Off"},
            blocking=True,
        )
    assert excinfo.value.translation_key == "invalid_system_mode"


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_permanent_with_duration(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test set_system_mode rejects duration/period for permanent-only modes."""

    # "Auto" is canBeTemporary=False in the default fixture
    with pytest.raises(homeassistant.exceptions.ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {ATTR_MODE: "Auto", ATTR_DURATION: {"hours": 1}},
            blocking=True,
        )
    assert excinfo.value.translation_key == "mode_does_not_support_temporary"

    with pytest.raises(homeassistant.exceptions.ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {ATTR_MODE: "Auto", ATTR_PERIOD: {"days": 1}},
            blocking=True,
        )
    assert excinfo.value.translation_key == "mode_does_not_support_temporary"


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_duration_with_period(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test set_system_mode rejects period for a Duration-type mode."""

    # "AutoWithEco" has timingMode="Duration" — only duration is valid, not period
    with pytest.raises(homeassistant.exceptions.ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {ATTR_MODE: "AutoWithEco", ATTR_PERIOD: {"days": 1}},
            blocking=True,
        )
    assert excinfo.value.translation_key == "mode_does_not_support_period"


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_period_with_duration(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test set_system_mode rejects duration for a Period-type mode."""

    # "Away" has timingMode="Period" — only period is valid, not duration
    with pytest.raises(homeassistant.exceptions.ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {ATTR_MODE: "Away", ATTR_DURATION: {"hours": 1}},
            blocking=True,
        )
    assert excinfo.value.translation_key == "mode_does_not_support_duration"


# Domain-level service deprecation tests (calling without target)


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    "svc",
    [
        EvoService.REFRESH_SYSTEM,
        EvoService.RESET_SYSTEM,
    ],
)
async def test_tcs_service_without_target_creates_issue(
    hass: HomeAssistant,
    svc: EvoService,
    ctl_id: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that calling a TCS service without a target creates a deprecation issue."""

    issue_id = f"deprecated_service_without_target_{svc}"

    with (
        patch("evohomeasync2.location.Location.update"),
        patch("evohomeasync2.control_system.ControlSystem.reset"),
    ):
        await hass.services.async_call(
            DOMAIN,
            svc,
            {},
            blocking=True,
        )

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "deprecated_service_without_target"


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_without_target_creates_issue(
    hass: HomeAssistant,
    ctl_id: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that calling set_system_mode without a target creates a deprecation issue."""

    issue_id = f"deprecated_service_without_target_{EvoService.SET_SYSTEM_MODE}"

    with patch("evohomeasync2.control_system.ControlSystem.set_mode"):
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {ATTR_MODE: "Auto"},
            blocking=True,
        )

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "deprecated_service_without_target"


@pytest.mark.parametrize("install", ["default"])
async def test_tcs_service_with_target_no_issue(
    hass: HomeAssistant,
    ctl_id: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that calling a TCS service with a target does not create an issue."""

    with patch("evohomeasync2.location.Location.update"):
        await hass.services.async_call(
            DOMAIN,
            EvoService.REFRESH_SYSTEM,
            {CONF_TARGET: {ATTR_ENTITY_ID: [ctl_id]}},
            blocking=True,
        )

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{EvoService.REFRESH_SYSTEM}"
    )
    assert issue is None


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    "svc",
    [
        EvoService.REFRESH_SYSTEM,
        EvoService.RESET_SYSTEM,
    ],
)
async def test_tcs_service_with_wrong_entity_id(
    hass: HomeAssistant,
    svc: EvoService,
    zone_id: str,
) -> None:
    """Test that calling a TCS service with a non-controller entity_id raises."""

    with pytest.raises(homeassistant.exceptions.ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            svc,
            {CONF_TARGET: {ATTR_ENTITY_ID: [zone_id]}},
            blocking=True,
        )

    assert excinfo.value.translation_key == "controller_only_service"


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_with_wrong_entity_id(
    hass: HomeAssistant,
    zone_id: str,
) -> None:
    """Test that calling set_system_mode with a non-controller entity_id raises."""

    with pytest.raises(homeassistant.exceptions.ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {ATTR_MODE: "Auto", CONF_TARGET: {ATTR_ENTITY_ID: [zone_id]}},
            blocking=True,
        )

    assert excinfo.value.translation_key == "controller_only_service"


# Entity-level service call tests (zone services)


@pytest.mark.parametrize("install", ["default"])
async def test_zone_clear_zone_override(
    hass: HomeAssistant,
    zone_id: str,
) -> None:
    """Test Evohome's clear_zone_override service (for a heating zone)."""

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
@pytest.mark.parametrize(
    ("svc", "service_data"),
    [
        (EvoService.CLEAR_ZONE_OVERRIDE, {}),
        (EvoService.SET_ZONE_OVERRIDE, {ATTR_SETPOINT: 20.0}),
    ],
)
async def test_zone_services_with_ctl_id(
    hass: HomeAssistant,
    svc: EvoService,
    service_data: dict,
    ctl_id: str,
) -> None:
    """Test that calling zone services on a controller raises ServiceValidationError."""

    with pytest.raises(homeassistant.exceptions.ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            svc,
            service_data,
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )
    assert excinfo.value.translation_key == "zone_only_service"
