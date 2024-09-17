"""The tests for evohome services.

Assert service calls my mocking the HTTP GET/PUTs and checking the URL/payloads.

The payload (json) of some requests (to the vendor API) are difficult to assert
because they contain datetimes relative to a particular zone's scheduled setpoint.
Instead, they are collected here, so that they can be simply asserted via snapshot.
"""

from __future__ import annotations

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.evohome import DOMAIN, EvoService
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import entity_of_ctl, entity_of_zone, setup_evohome
from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_evohome_svcs_ctl(
    hass: HomeAssistant,
    config: dict[str, str],
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    install: str,
) -> None:
    """Test domain-specific services of a evohome-compatible controller."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        services = list(hass.services.async_services_for_domain(DOMAIN))
        assert services == snapshot

        with patch("evohomeasync2.location.Location.refresh_status") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.REFRESH_SYSTEM,
                service_data=None,
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            assert mock_fcn.await_args.kwargs == {}

        system_mode = "Off" if install == "h032585" else "HeatingOff"

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_SYSTEM_MODE,
                service_data={"mode": system_mode},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (system_mode,)
            assert mock_fcn.await_args.kwargs == {"until": None}

        if install == "h032585":  # only supports Heat, Off
            return results

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_SYSTEM_MODE,
                service_data={"mode": "Away", "period": {"days": 21}},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ("Away",)
            assert "until" in mock_fcn.await_args.kwargs

            results.append(mock_fcn.await_args.kwargs)

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_SYSTEM_MODE,
                service_data={"mode": "AutoWithEco", "duration": {"minutes": 150}},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ("AutoWithEco",)
            assert "until" in mock_fcn.await_args.kwargs

            results.append(mock_fcn.await_args.kwargs)

        if EvoService.RESET_SYSTEM not in services:
            return results

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            # mock_refresh.side_effect =

            await hass.services.async_call(
                DOMAIN,
                EvoService.RESET_SYSTEM,
                service_data=None,
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ("AutoWithReset",)
            assert mock_fcn.await_args.kwargs == {"until": None}

    assert results == snapshot  # noqa: RET503


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_evohome_svcs_zon(
    hass: HomeAssistant,
    config: dict[str, str],
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    install: str,
) -> None:
    """Test domain-specific services of a evohome-compatible climate zone."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        zone = entity_of_zone(hass)  # the first zone will do...

        # reset zone to follow_schedule
        with patch("evohomeasync2.zone.Zone.reset_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.RESET_ZONE_OVERRIDE,
                service_data={"entity_id": zone.entity_id},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            assert mock_fcn.await_args.kwargs == {}

        # set zone to temporary_override
        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_ZONE_OVERRIDE,
                service_data={
                    "entity_id": zone.entity_id,
                    "setpoint": 21.3,
                    "duration": {"minutes": 150},
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (21.3,)
            assert "until" in mock_fcn.await_args.kwargs

            results.append(mock_fcn.await_args.kwargs)

        # set zone to temporary_override (advance to next scheduled setpoint)
        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_ZONE_OVERRIDE,
                service_data={
                    "entity_id": zone.entity_id,
                    "setpoint": 19.7,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (19.7,)
            assert (
                "until" in mock_fcn.await_args.kwargs
            )  # until next scheduled setpoint

            results.append(mock_fcn.await_args.kwargs)  # varies by install fixture/zone

        # # set zone to permanent_override
        # with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        # await hass.services.async_call(
        #     DOMAIN,
        #     EvoService.SET_ZONE_OVERRIDE,
        #     service_data={
        #         "entity_id": zone.entity_id,
        #         "setpoint": 19.7,
        #         "duration": None,
        #     },
        #     blocking=True,
        # )

        # assert mock_fcn.await_count == 1
        # assert mock_fcn.await_args.args == (19.7,)
        # assert "until" in mock_fcn.await_args.kwargs  # until next scheduled setpoint

        # results.append(mock_fcn.await_args.kwargs)  # varies by install fixture/zone

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_climate_svcs_ctl(
    hass: HomeAssistant,
    config: dict[str, str],
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    install: str,
) -> None:
    """Test climate services of a evohome-compatible controller."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        ctl = entity_of_ctl(hass)

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_HVAC_MODE,
                {
                    ATTR_ENTITY_ID: ctl.entity_id,
                    ATTR_HVAC_MODE: HVACMode.OFF,
                },
                blocking=True,
            )

            system_mode = "Off" if install == "h032585" else "HeatingOff"

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (system_mode,)
            assert mock_fcn.await_args.kwargs == {"until": None}

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_HVAC_MODE,
                {
                    ATTR_ENTITY_ID: ctl.entity_id,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
                blocking=True,
            )

            system_mode = "Heat" if install == "h032585" else "Auto"

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (system_mode,)
            assert mock_fcn.await_args.kwargs == {"until": None}

        for hvac_mode in HVACMode:
            if hvac_mode in (HVACMode.HEAT, HVACMode.OFF):
                continue

            with pytest.raises(HomeAssistantError):
                await hass.services.async_call(
                    Platform.CLIMATE,
                    SERVICE_SET_HVAC_MODE,
                    {
                        ATTR_ENTITY_ID: ctl.entity_id,
                        ATTR_HVAC_MODE: hvac_mode,
                    },
                    blocking=True,
                )

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_water_heater_svcs_dhw(
    hass: HomeAssistant,
    config: dict[str, str],
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    install: str,
) -> None:
    """Test water_heater services of a evohome-compatible DHW zone."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        zone = entity_of_zone(hass)  # the first zone will do...

        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_TEMPERATURE,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                    ATTR_TEMPERATURE: 21.5,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (21.5,)
            assert (
                "until" in mock_fcn.await_args.kwargs
            )  # until next scheduled setpoint

            results.append(mock_fcn.await_args.kwargs)  # varies by install fixture/zone

        for temperature in (0, 40):
            with pytest.raises(ServiceValidationError):
                await hass.services.async_call(
                    Platform.CLIMATE,
                    SERVICE_SET_TEMPERATURE,
                    {
                        ATTR_ENTITY_ID: zone.entity_id,
                        ATTR_TEMPERATURE: temperature,
                    },
                    blocking=True,
                )

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_climate_svcs_zon(
    hass: HomeAssistant,
    config: dict[str, str],
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    install: str,
) -> None:
    """Test climate services of a evohome-compatible climate zone."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        zone = entity_of_zone(hass)  # the first zone will do...

        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_TEMPERATURE,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                    ATTR_TEMPERATURE: 21.5,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (21.5,)
            assert (
                "until" in mock_fcn.await_args.kwargs
            )  # until next scheduled setpoint

            results.append(mock_fcn.await_args.kwargs)  # varies by install fixture/zone

        for temperature in (0, 40):
            with pytest.raises(ServiceValidationError):
                await hass.services.async_call(
                    Platform.CLIMATE,
                    SERVICE_SET_TEMPERATURE,
                    {
                        ATTR_ENTITY_ID: zone.entity_id,
                        ATTR_TEMPERATURE: temperature,
                    },
                    blocking=True,
                )

    assert results == snapshot
