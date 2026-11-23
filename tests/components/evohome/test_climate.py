"""The tests for the climate platform of evohome.

All evohome systems have controllers and at least one zone.
"""

from datetime import timedelta
from unittest.mock import patch

from evohomeasync2 import exceptions as evo_exc
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateService,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import setup_evohome
from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", [*TEST_INSTALLS, "botched"])
async def test_setup_platform(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities and their states after setup of evohome."""

    # Cannot use the evohome fixture here, as need to set dtm first
    #  - some extended state attrs are relative the current time
    freezer.move_to("2024-07-10T12:00:00Z")

    async for _ in setup_evohome(hass, config, install=install):
        pass

    climate_states = hass.states.async_all(CLIMATE_DOMAIN)
    assert climate_states

    for x in climate_states:
        assert x == snapshot(name=f"{x.entity_id}-state")


@pytest.mark.parametrize("install", ["default"])
async def test_entities_update_over_time(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test extended attributes update as time passes.

    Verifies that time-dependent state attrs (e.g. schedules) vary as time advances.
    """

    # Cannot use the evohome fixture here, as need to set dtm first
    #  - some extended state attrs are relative the current time
    freezer.move_to("2024-07-10T05:30:00Z")

    # stay inside this context to have the mocked RESTful API
    async for _ in setup_evohome(hass, config, install=install):
        for x in hass.states.async_all(CLIMATE_DOMAIN):
            assert x == snapshot(name=f"{x.entity_id}-state-initial")

        freezer.tick(timedelta(hours=12))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        for x in hass.states.async_all(CLIMATE_DOMAIN):
            assert x == snapshot(name=f"{x.entity_id}-state-updated")


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_ctl_set_hvac_mode(
    hass: HomeAssistant,
    ctl_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test ClimateService.SET_HVAC_MODE of an evohome controller."""

    results = []

    # ClimateService.SET_HVAC_MODE: HVACMode.OFF
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: ctl_id,
                ClimateServiceArgument.HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )

        try:
            mock_fcn.assert_awaited_once_with("heating_off", until=None)
        except AssertionError:
            mock_fcn.assert_awaited_once_with("off", until=None)

        results.append(mock_fcn.await_args.args)  # type: ignore[union-attr]

    # ClimateService.SET_HVAC_MODE: HVACMode.HEAT
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: ctl_id,
                ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

        try:
            mock_fcn.assert_awaited_once_with("auto", until=None)
        except AssertionError:
            mock_fcn.assert_awaited_once_with("heat", until=None)

        results.append(mock_fcn.await_args.args)  # type: ignore[union-attr]

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_ctl_set_temperature(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test ClimateService.SET_TEMPERATURE of an evohome controller."""

    # Entity climate.xxx does not support this service
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: ctl_id,
                ClimateServiceArgument.TEMPERATURE: 19.1,
            },
            blocking=True,
        )


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_ctl_turn_off(
    hass: HomeAssistant,
    ctl_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test ClimateService.TURN_OFF of an evohome controller."""

    results = []

    # ClimateService.TURN_OFF
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.TURN_OFF,
            {
                TargetKey.ENTITY_ID: ctl_id,
            },
            blocking=True,
        )

        try:
            mock_fcn.assert_awaited_once_with("heating_off", until=None)
        except AssertionError:
            mock_fcn.assert_awaited_once_with("off", until=None)

        results.append(mock_fcn.await_args.args)  # type: ignore[union-attr]

    assert results == snapshot


@pytest.mark.parametrize("install", ["default"])
async def test_ctl_invalid_system_mode(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test translated exception when the requested system mode is invalid."""

    with (
        patch(
            "evohomeasync2.control_system.ControlSystem.set_mode",
            side_effect=evo_exc.InvalidModeRequestError("Unsupported mode: xxx"),
        ),
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.TURN_OFF,
            {
                TargetKey.ENTITY_ID: ctl_id,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_system_mode"


@pytest.mark.parametrize("install", ["default"])
async def test_ctl_authentication_failed(
    hass: HomeAssistant,
    ctl_id: str,
) -> None:
    """Test an authentication failure is raised as a translated error."""

    with (
        patch(
            "evohomeasync2.control_system.ControlSystem.set_mode",
            side_effect=evo_exc.BadUserCredentialsError("Authentication failed"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.TURN_OFF,
            {
                TargetKey.ENTITY_ID: ctl_id,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "api_credentials_invalid"


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_ctl_turn_on(
    hass: HomeAssistant,
    ctl_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test ClimateService.TURN_ON of an evohome controller."""

    results = []

    # ClimateService.TURN_ON
    with patch("evohomeasync2.control_system.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.TURN_ON,
            {
                TargetKey.ENTITY_ID: ctl_id,
            },
            blocking=True,
        )

        try:
            mock_fcn.assert_awaited_once_with("auto", until=None)
        except AssertionError:
            mock_fcn.assert_awaited_once_with("heat", until=None)

        results.append(mock_fcn.await_args.args)  # type: ignore[union-attr]

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_zone_set_hvac_mode(
    hass: HomeAssistant,
    zone_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test ClimateService.SET_HVAC_MODE of an evohome heating zone."""

    results = []

    # ClimateService.SET_HVAC_MODE: HVACMode.HEAT
    with patch("evohomeasync2.zone.Zone.reset") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: zone_id,
                ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()

    # ClimateService.SET_HVAC_MODE: HVACMode.OFF
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: zone_id,
                ClimateServiceArgument.HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once()

        assert mock_fcn.await_args is not None  # mypy hint
        assert mock_fcn.await_args.args != ()  # minimum target temp
        assert mock_fcn.await_args.kwargs == {"until": None}

        results.append(mock_fcn.await_args.args)

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_zone_set_preset_mode(
    hass: HomeAssistant,
    zone_id: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test ClimateService.SET_PRESET_MODE of an evohome heating zone."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    # ClimateService.SET_PRESET_MODE: none
    with patch("evohomeasync2.zone.Zone.reset") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: zone_id,
                ClimateServiceArgument.PRESET_MODE: "none",
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()

    # ClimateService.SET_PRESET_MODE: permanent
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: zone_id,
                ClimateServiceArgument.PRESET_MODE: "permanent",
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once()

        assert mock_fcn.await_args is not None  # mypy hint
        assert mock_fcn.await_args.args != ()  # current target temp
        assert mock_fcn.await_args.kwargs == {"until": None}

        results.append(mock_fcn.await_args.args)

    # ClimateService.SET_PRESET_MODE: temporary
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: zone_id,
                ClimateServiceArgument.PRESET_MODE: "temporary",
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once()

        assert mock_fcn.await_args is not None  # mypy hint
        assert mock_fcn.await_args.args != ()  # current target temp
        assert mock_fcn.await_args.kwargs != {}  # next setpoint dtm

        results.append(mock_fcn.await_args.args)
        results.append(mock_fcn.await_args.kwargs)

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_zone_set_temperature(
    hass: HomeAssistant,
    zone_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test ClimateService.SET_TEMPERATURE of an evohome heating zone."""

    results = []

    # ClimateService.SET_TEMPERATURE: temperature
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: zone_id,
                ClimateServiceArgument.TEMPERATURE: 19.1,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once()

        assert mock_fcn.await_args is not None  # mypy hint
        assert mock_fcn.await_args.args == (19.1,)
        assert mock_fcn.await_args.kwargs != {}  # next setpoint dtm

        results.append(mock_fcn.await_args.kwargs)

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_zone_turn_off(
    hass: HomeAssistant,
    zone_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test ClimateService.TURN_OFF of an evohome heating zone."""

    results = []

    # ClimateService.TURN_OFF
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.TURN_OFF,
            {
                TargetKey.ENTITY_ID: zone_id,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once()

        assert mock_fcn.await_args is not None  # mypy hint
        assert mock_fcn.await_args.args != ()  # minimum target temp
        assert mock_fcn.await_args.kwargs == {"until": None}

        results.append(mock_fcn.await_args.args)

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_zone_turn_on(
    hass: HomeAssistant,
    zone_id: str,
) -> None:
    """Test ClimateService.TURN_ON of an evohome heating zone."""

    # ClimateService.TURN_ON
    with patch("evohomeasync2.zone.Zone.reset") as mock_fcn:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.TURN_ON,
            {
                TargetKey.ENTITY_ID: zone_id,
            },
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()
