"""The tests for evohome services.

Evohome implements some domain-specific service.
"""

from __future__ import annotations

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.evohome import DOMAIN, EvoService
from homeassistant.components.water_heater import (
    ATTR_AWAY_MODE,
    ATTR_OPERATION_MODE,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_OPERATION_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .conftest import ctl_entity, dhw_entity, setup_evohome, zone_entity
from .const import CTL_MODE_LOOKUP, TEST_INSTALLS


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_evohome_ctl_svcs(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test domain-specific services of a evohome-compatible controller."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        ctl = ctl_entity(hass)

        services = list(hass.services.async_services_for_domain(DOMAIN))
        assert services == snapshot

        # EvoService.REFRESH_SYSTEM
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

        # EvoService.SET_SYSTEM_MODE: HeatingOff (or Off)
        ctl_mode = "Off" if "Off" in ctl._modes else "HeatingOff"  # most are HeatingOff

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_SYSTEM_MODE,
                service_data={"mode": ctl_mode},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (ctl_mode,)
            assert mock_fcn.await_args.kwargs == {
                "until": None,
            }

        # EvoService.SET_SYSTEM_MODE: Auto (or Heat)
        ctl_mode = "Auto" if "Auto" in ctl._modes else "Heat"  # most are Auto

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_SYSTEM_MODE,
                service_data={"mode": ctl_mode},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (ctl_mode,)
            assert mock_fcn.await_args.kwargs == {
                "until": None,
            }

        # some systems (e.g. VisionPro Wifi) support only Off, Heat
        if not [
            m for m in ctl._modes if m not in ("Auto", "Heat", "HeatingOff", "Off")
        ]:
            return

        # EvoService.SET_SYSTEM_MODE: Away, for 21 days
        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_SYSTEM_MODE,
                service_data={"mode": "Away", "period": {"days": 21}},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ("Away",)
            assert install != "default" or mock_fcn.await_args.kwargs == {
                "until": dt_util.parse_datetime("2024-07-31T07:00:00Z")
            }

            results.append(mock_fcn.await_args.kwargs)

        # EvoService.SET_SYSTEM_MODE: AutoWithEco, for 150 minutes
        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_SYSTEM_MODE,
                service_data={"mode": "AutoWithEco", "duration": {"minutes": 150}},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ("AutoWithEco",)
            assert mock_fcn.await_args.kwargs == {
                "until": dt_util.parse_datetime("2024-07-10T14:30:00Z")
            }

        # only evohome (e.g. not RoundThermostat) supports AutoWithReset
        if "AutoWithReset" not in ctl._modes:
            # not need to confirm EvoService.RESET_SYSTEM not in services
            return

        # EvoService.RESET_SYSTEM
        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.RESET_SYSTEM,
                service_data=None,
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ("AutoWithReset",)
            assert mock_fcn.await_args.kwargs == {"until": None}

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_evohome_zon_svcs(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test domain-specific services of a evohome-compatible climate zone."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        zone = zone_entity(hass)

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
                    "setpoint": 20.1,
                    "duration": {"minutes": 150},
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (20.1,)
            assert mock_fcn.await_args.kwargs == {
                "until": dt_util.parse_datetime("2024-07-10T14:30:00Z")
            }

        # set zone to temporary_override (advance to next scheduled setpoint)
        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_ZONE_OVERRIDE,
                service_data={
                    "entity_id": zone.entity_id,
                    "setpoint": 20.2,
                    "duration": 0,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (20.2,)
            assert install != "default" or mock_fcn.await_args.kwargs == {
                "until": dt_util.parse_datetime("2024-07-10T21:10:00Z"),
            }

            results.append(mock_fcn.await_args.kwargs)

        # set zone to permanent_override
        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_ZONE_OVERRIDE,
                service_data={
                    "entity_id": zone.entity_id,
                    "setpoint": 20.3,
                },
                blocking=True,
            )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == (20.3,)
        assert mock_fcn.await_args.kwargs == {
            "until": None,
        }

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_climate_ctl_svcs(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate services of a evohome-compatible controller."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        ctl = ctl_entity(hass)

        assert ctl.hvac_modes == [HVACMode.OFF, HVACMode.HEAT]

        # SERVICE_SET_HVAC_MODE: HVACMode.OFF
        ctl_mode = "HeatingOff" if "HeatingOff" in ctl._modes else "Off"

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

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (ctl_mode,)
            assert mock_fcn.await_args.kwargs == {"until": None}

        # SERVICE_SET_HVAC_MODE: HVACMode.HEAT
        ctl_mode = "Heat" if "Heat" in ctl._modes else "Auto"

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

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (ctl_mode,)
            assert mock_fcn.await_args.kwargs == {"until": None}

        assert install != "default" or ctl.preset_modes == list(CTL_MODE_LOOKUP)
        assert ctl.preset_modes == snapshot

        # SERVICE_SET_PRESET_MODE: various
        for mode in ctl.preset_modes or []:  # could be None
            with patch(
                "evohomeasync2.controlsystem.ControlSystem.set_mode"
            ) as mock_fcn:
                await hass.services.async_call(
                    Platform.CLIMATE,
                    SERVICE_SET_PRESET_MODE,
                    {
                        ATTR_ENTITY_ID: ctl.entity_id,
                        ATTR_PRESET_MODE: mode,
                    },
                    blocking=True,
                )

                assert mock_fcn.await_count == 1
                assert install != "default" or mock_fcn.await_args.args == (
                    CTL_MODE_LOOKUP[mode],
                )
                assert mock_fcn.await_args.kwargs == {"until": None}

                results.append(mock_fcn.await_args.args)

        # SERVICE_SET_TEMPERATURE (not supported)
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_TEMPERATURE,
                {
                    ATTR_ENTITY_ID: ctl.entity_id,
                    ATTR_TEMPERATURE: 23.0,
                },
                blocking=True,
            )

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_climate_zon_svcs(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate services of a evohome-compatible climate zone."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        zone = zone_entity(hass)

        assert zone.preset_modes == ["none", "temporary", "permanent"]

        # SERVICE_SET_PRESET_MODE: "none"
        with patch("evohomeasync2.zone.Zone.reset_mode") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_PRESET_MODE,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                    ATTR_PRESET_MODE: "none",
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            assert mock_fcn.await_args.kwargs == {}

        # SERVICE_SET_PRESET_MODE: "permanent"
        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_PRESET_MODE,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                    ATTR_PRESET_MODE: "permanent",
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert install != "default" or mock_fcn.await_args.args == (17.0,)
            assert mock_fcn.await_args.kwargs == {
                "until": None,
            }

            results.append(mock_fcn.await_args.args)

        # SERVICE_SET_PRESET_MODE: "temporary"
        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_PRESET_MODE,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                    ATTR_PRESET_MODE: "temporary",
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert install != "default" or mock_fcn.await_args.args == (17.0,)
            assert install != "default" or mock_fcn.await_args.kwargs == {
                "until": dt_util.parse_datetime("2024-07-10T21:10:00Z")
            }

            results.append(mock_fcn.await_args)

        # SERVICE_SET_TEMPERATURE: 23.0
        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_TEMPERATURE,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                    ATTR_TEMPERATURE: 23.0,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (23.0,)
            assert "until" in mock_fcn.await_args.kwargs  # to next scheduled setpoint

            results.append(mock_fcn.await_args.kwargs)  # varies by install fixture/zone

        for temperature in (0, 40):  # outside of min/max temp range
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

        assert zone.hvac_modes == [HVACMode.OFF, HVACMode.HEAT]

        # SERVICE_SET_HVAC_MODE: HVACMode.OFF
        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_HVAC_MODE,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                    ATTR_HVAC_MODE: HVACMode.OFF,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (zone.min_temp,)
            assert mock_fcn.await_args.kwargs == {"until": None}

        # SERVICE_SET_HVAC_MODE: HVACMode.HEAT
        with patch("evohomeasync2.zone.Zone.reset_mode") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_SET_HVAC_MODE,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            assert mock_fcn.await_args.kwargs == {}

        # SERVICE_TURN_OFF
        with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (zone.min_temp,)
            assert mock_fcn.await_args.kwargs == {"until": None}

        # SERVICE_TURN_ON
        with patch("evohomeasync2.zone.Zone.reset_mode") as mock_fcn:
            await hass.services.async_call(
                Platform.CLIMATE,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: zone.entity_id,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            assert mock_fcn.await_args.kwargs == {}

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_water_heater_svcs(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test water_heater services of a evohome-compatible DHW zone."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        if (dhw := dhw_entity(hass)) is None:
            pytest.skip("this installation has no DHW to test")

        # SERVICE_SET_AWAY_MODE: False (FollowSchedule)
        with patch("evohomeasync2.hotwater.HotWater.reset_mode") as mock_fcn:
            await hass.services.async_call(
                Platform.WATER_HEATER,
                SERVICE_SET_AWAY_MODE,
                {
                    ATTR_ENTITY_ID: dhw.entity_id,
                    ATTR_AWAY_MODE: False,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            assert mock_fcn.await_args.kwargs == {}

        # SERVICE_SET_AWAY_MODE: True (PermanentOverride/Off)
        with patch("evohomeasync2.hotwater.HotWater.set_off") as mock_fcn:
            await hass.services.async_call(
                Platform.WATER_HEATER,
                SERVICE_SET_AWAY_MODE,
                {
                    ATTR_ENTITY_ID: dhw.entity_id,
                    ATTR_AWAY_MODE: True,
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            assert mock_fcn.await_args.kwargs == {}

        assert dhw.operation_list == ["auto", "on", "off"]

        # SERVICE_SET_OPERATION_MODE: "auto" (FollowSchedule)
        with patch("evohomeasync2.hotwater.HotWater.reset_mode") as mock_fcn:
            await hass.services.async_call(
                Platform.WATER_HEATER,
                SERVICE_SET_OPERATION_MODE,
                {
                    ATTR_ENTITY_ID: dhw.entity_id,
                    ATTR_OPERATION_MODE: "auto",
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            assert mock_fcn.await_args.kwargs == {}

        # SERVICE_SET_OPERATION_MODE: "off" (TemporaryOverride/Off)
        with patch("evohomeasync2.hotwater.HotWater.set_off") as mock_fcn:
            await hass.services.async_call(
                Platform.WATER_HEATER,
                SERVICE_SET_OPERATION_MODE,
                {
                    ATTR_ENTITY_ID: dhw.entity_id,
                    ATTR_OPERATION_MODE: "off",
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            results.append(mock_fcn.await_args.kwargs)

        # SERVICE_SET_OPERATION_MODE: "on" (TemporaryOverride/On)
        with patch("evohomeasync2.hotwater.HotWater.set_on") as mock_fcn:
            await hass.services.async_call(
                Platform.WATER_HEATER,
                SERVICE_SET_OPERATION_MODE,
                {
                    ATTR_ENTITY_ID: dhw.entity_id,
                    ATTR_OPERATION_MODE: "on",
                },
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == ()
            results.append(mock_fcn.await_args.kwargs)

        for service in (SERVICE_TURN_OFF, SERVICE_TURN_ON):
            with pytest.raises(HomeAssistantError):
                await hass.services.async_call(
                    Platform.WATER_HEATER,
                    service,
                    {
                        ATTR_ENTITY_ID: dhw.entity_id,
                    },
                    blocking=True,
                )

    assert results == snapshot
