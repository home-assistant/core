"""The tests for evohome services.

Evohome implements some domain-specific service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    SERVICE_SET_HVAC_MODE,
    HVACMode,
)
from homeassistant.components.evohome import DOMAIN, EvoService
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from .conftest import ctl_entity, setup_evohome
from .const import TEST_INSTALLS

if TYPE_CHECKING:
    from homeassistant.components.evohome.climate import EvoController


CTL_MODE_LOOKUP = {
    "Reset": "AutoWithReset",
    "eco": "AutoWithEco",
    "away": "Away",
    "home": "DayOff",
    "Custom": "Custom",
}


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

    async for _ in setup_evohome(hass, config, install=install):
        ctl: EvoController = ctl_entity(hass)

        services = list(hass.services.async_services_for_domain(DOMAIN))
        assert services == snapshot

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

    async for _ in setup_evohome(hass, config, install=install):
        ctl: EvoController = ctl_entity(hass)

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
