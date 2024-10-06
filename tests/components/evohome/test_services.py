"""The tests for evohome services.

Evohome implements some domain-specific service.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    SERVICE_SET_HVAC_MODE,
    HVACMode,
)
from homeassistant.components.evohome import DOMAIN, EvoService
from homeassistant.components.evohome.climate import EvoController
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from .conftest import extract_ctl_from_locations_config, get_ctl_entity, setup_evohome
from .const import TEST_INSTALLS

CTL_MODE_LOOKUP = {
    "Reset": "AutoWithReset",
    "eco": "AutoWithEco",
    "away": "Away",
    "home": "DayOff",
    "Custom": "Custom",
}


def extract_heat_mode_from_location(
    config: dict[str, str],
    install: str,
) -> str:
    """Return the heating on mode from the config JSON of a chosen controller."""

    ctl = extract_ctl_from_locations_config(config, install)
    modes = [d["systemMode"] for d in ctl["allowedSystemModes"]]
    return "Heat" if "Heat" in modes else "Auto"  # "Heat" is an edge-case


def extract_off_mode_from_location(
    config: dict[str, str],
    install: str,
) -> str:
    """Return the heating off mode from the config JSON of a chosen controller."""

    ctl = extract_ctl_from_locations_config(config, install)
    modes = [d["systemMode"] for d in ctl["allowedSystemModes"]]
    return "Off" if "Off" in modes else "HeatingOff"  # "Off" is an edge-case


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_evohome_ctl_svcs(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test domain-specific services of a evohome-compatible controller."""

    async for _ in setup_evohome(hass, config, install=install):
        services = list(hass.services.async_services_for_domain(DOMAIN))
        assert services == snapshot

        # EvoService.SET_SYSTEM_MODE: 'HeatingOff' (or 'Off')
        ctl_mode = extract_off_mode_from_location(config, install)

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_SYSTEM_MODE,
                service_data={"mode": ctl_mode},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (ctl_mode,)
            assert mock_fcn.await_args.kwargs == {"until": None}

        # EvoService.SET_SYSTEM_MODE: 'Auto' (or 'Heat')
        ctl_mode = extract_heat_mode_from_location(config, install)

        with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
            await hass.services.async_call(
                DOMAIN,
                EvoService.SET_SYSTEM_MODE,
                service_data={"mode": ctl_mode},
                blocking=True,
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (ctl_mode,)
            assert mock_fcn.await_args.kwargs == {"until": None}


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_climate_ctl_svcs(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate services of a evohome-compatible controller."""

    async for _ in setup_evohome(hass, config, install=install):
        ctl: EvoController = get_ctl_entity(hass)

        assert ctl._evo_modes == snapshot
        assert ctl.hvac_modes == [HVACMode.OFF, HVACMode.HEAT]
        assert ctl.preset_modes == snapshot

        # SERVICE_SET_HVAC_MODE: HVACMode.OFF
        ctl_mode = extract_off_mode_from_location(config, install)

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
        ctl_mode = extract_heat_mode_from_location(config, install)

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
