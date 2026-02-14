"""The tests for the native services of Evohome."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components.evohome.const import (
    ATTR_DURATION,
    ATTR_PERIOD,
    ATTR_SETPOINT,
    DOMAIN,
    EvoService,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir

TCS_SERVICES_WITH_MOCKS = [
    (EvoService.REFRESH_SYSTEM, "evohomeasync2.location.Location.update"),
    (EvoService.RESET_SYSTEM, "evohomeasync2.control_system.ControlSystem.reset"),
]


# Domain-level service call tests (for a controller/TCS)
# these service calls use {"target": ...}


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(("svc", "mock_path"), TCS_SERVICES_WITH_MOCKS)
async def test_tcs_services(
    hass: HomeAssistant,
    ctl_id: str,
    svc: EvoService,
    mock_path: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test calling TCS services with a target."""

    with patch(mock_path) as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            svc,
            {},
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{svc}"
    )
    assert issue is None


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode(
    hass: HomeAssistant,
    ctl_id: str,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test calling set_system_mode call with a target."""

    # EvoService.SET_SYSTEM_MODE: Auto
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Auto",
            },
            target={ATTR_ENTITY_ID: ctl_id},
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
            target={ATTR_ENTITY_ID: ctl_id},
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
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with(
            "Away", until=datetime(2024, 7, 16, 23, 0, tzinfo=UTC)
        )

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{EvoService.SET_SYSTEM_MODE}"
    )
    assert issue is None


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_invalid_mode(  # ServiceValidationError
    hass: HomeAssistant,
    ctl_id: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test set_system_mode rejects a mode not in the allowed system modes."""

    # "Off" is not in the default fixture's allowed system modes
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Off",
            },
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "invalid_system_mode"

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{EvoService.SET_SYSTEM_MODE}"
    )
    assert issue is None


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_permanent_with_duration(  # ServiceValidationError
    hass: HomeAssistant,
    ctl_id: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test set_system_mode rejects duration/period for permanent-only modes."""

    # "Auto" is canBeTemporary=False in the default fixture
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Auto",
                ATTR_DURATION: {"hours": 1},
            },
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "mode_does_not_support_temporary"

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Auto",
                ATTR_PERIOD: {"days": 1},
            },
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "mode_does_not_support_temporary"

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{EvoService.SET_SYSTEM_MODE}"
    )
    assert issue is None


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_duration_with_period(  # ServiceValidationError
    hass: HomeAssistant,
    ctl_id: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test set_system_mode rejects period for a duration-type mode."""

    # "AutoWithEco" has timingMode="Duration" — only duration is valid, not period
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "AutoWithEco",
                ATTR_PERIOD: {"days": 1},
            },
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "mode_does_not_support_period"

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{EvoService.SET_SYSTEM_MODE}"
    )
    assert issue is None


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_period_with_duration(  # ServiceValidationError
    hass: HomeAssistant,
    ctl_id: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test set_system_mode rejects duration for a period-type mode."""

    # "Away" has timingMode="Period" — only period is valid, not duration
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Away",
                ATTR_DURATION: {"hours": 1},
            },
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "mode_does_not_support_duration"

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{EvoService.SET_SYSTEM_MODE}"
    )
    assert issue is None


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_both_duration_and_period(  # vol.MultipleInvalid
    hass: HomeAssistant,
    ctl_id: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test set_system_mode rejects both duration and period."""

    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Away",
                ATTR_DURATION: {"hours": 12},
                ATTR_PERIOD: {"days": 7},
            },
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{EvoService.SET_SYSTEM_MODE}"
    )
    assert issue is None


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    "svc",
    [t[0] for t in TCS_SERVICES_WITH_MOCKS],
)
async def test_tcs_services_with_wrong_entity_id(  # ServiceValidationError
    hass: HomeAssistant,
    svc: EvoService,
    zone_id: str,
) -> None:
    """Test calling a TCS services with a non-TCS entity_id fails."""

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            svc,
            {},
            target={ATTR_ENTITY_ID: zone_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "controller_only_service"


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_with_wrong_entity_id(  # ServiceValidationError
    hass: HomeAssistant,
    zone_id: str,
) -> None:
    """Test calling set_system_mode with a non-TCS entity_id fails."""

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            {
                ATTR_MODE: "Auto",
            },
            target={ATTR_ENTITY_ID: zone_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "controller_only_service"


# Domain-level service deprecation tests (calling without target)


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(("svc", "mock_path"), TCS_SERVICES_WITH_MOCKS)
async def test_tcs_services_deprecated(
    hass: HomeAssistant,
    ctl_id: str,
    svc: EvoService,
    mock_path: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test calling TCS services without a target creates an issue."""

    with patch(mock_path) as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            svc,
            {},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{svc}"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_service_without_target"


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_deprecated(
    hass: HomeAssistant,
    ctl_id: str,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test calling set_system_mode without a target creates an issue."""

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

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_service_without_target_{EvoService.SET_SYSTEM_MODE}"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_service_without_target"


@pytest.mark.parametrize("install", ["default"])
async def test_set_system_mode_both_duration_and_period_deprecated(  # vol.MultipleInvalid
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test set_system_mode rejects both duration and period (without target)."""

    with pytest.raises(vol.MultipleInvalid):
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


# Entity-level service call tests (for a zone)
# these service calls use target=...


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
async def test_zone_clear_zone_override_with_ctl_id(  # ServiceValidationError
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test calling a zone service with a non-zone entity_id fails."""

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            EvoService.CLEAR_ZONE_OVERRIDE,
            {},
            target={ATTR_ENTITY_ID: ctl_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "zone_only_service"
