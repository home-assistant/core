"""The tests for climate entities of evohome.

There are two distinct types of such entities, controllers and zones.
"""

from __future__ import annotations

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import setup_evohome, zone_entity
from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_set_hvac_mode_zone(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate methods of a evohome-compatible zone."""

    # some dtm are relative to a schedule
    freezer.move_to("2024-07-10T12:00:00Z")
    result = []

    async for _ in setup_evohome(hass, config, install=install):
        zone = zone_entity(hass)

        assert zone.hvac_modes == [HVACMode.OFF, HVACMode.HEAT]

        with patch("evohomeasync2.zone.Zone._set_mode") as mock_fcn:
            await zone.async_set_hvac_mode(HVACMode.HEAT)

            assert mock_fcn.await_count == 1
            assert install != "default" or mock_fcn.await_args.args == (
                {
                    "setpointMode": "FollowSchedule",
                },
            )
            assert mock_fcn.await_args.kwargs == {}

        with patch("evohomeasync2.zone.Zone._set_mode") as mock_fcn:
            await zone.async_set_hvac_mode(HVACMode.OFF)

            assert mock_fcn.await_count == 1
            assert install != "default" or mock_fcn.await_args.args == (
                {
                    "setpointMode": "PermanentOverride",
                    "HeatSetpointValue": 5.0,  # varies by install
                },
            )
            assert mock_fcn.await_args.kwargs == {}

            result.append(mock_fcn.await_args.args)

    assert result == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_set_preset_mode_zone(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate methods of a evohome-compatible zone."""

    # some dtm are relative to a schedule
    freezer.move_to("2024-07-10T12:00:00Z")
    result = []

    async for _ in setup_evohome(hass, config, install=install):
        zone = zone_entity(hass)

        assert zone.preset_modes == ["none", "temporary", "permanent"]

        with patch("evohomeasync2.zone.Zone._set_mode") as mock_fcn:
            await zone.async_set_preset_mode("none")

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (
                {
                    "setpointMode": "FollowSchedule",
                },
            )
            assert mock_fcn.await_args.kwargs == {}

        with patch("evohomeasync2.zone.Zone._set_mode") as mock_fcn:
            await zone.async_set_preset_mode("permanent")

            assert mock_fcn.await_count == 1
            assert install != "default" or mock_fcn.await_args.args == (
                {
                    "setpointMode": "PermanentOverride",
                    "HeatSetpointValue": 17.0,  # varies by install
                },
            )
            assert mock_fcn.await_args.kwargs == {}

            result.append(mock_fcn.await_args.args)

        with patch("evohomeasync2.zone.Zone._set_mode") as mock_fcn:
            await zone.async_set_preset_mode("temporary")

            assert mock_fcn.await_count == 1
            assert install != "default" or mock_fcn.await_args.args == (
                {
                    "setpointMode": "TemporaryOverride",
                    "HeatSetpointValue": 17.0,  # varies by install
                    "timeUntil": "2024-07-10T21:10:00Z",  # varies by install
                },
            )
            assert mock_fcn.await_args.kwargs == {}

            result.append(mock_fcn.await_args.args)

    assert result == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_set_temperature_zone(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate methods of a evohome-compatible zone."""

    # some dtm are relative to a schedule
    freezer.move_to("2024-07-10T12:00:00Z")
    result = []

    async for _ in setup_evohome(hass, config, install=install):
        zone = zone_entity(hass)

        with patch("evohomeasync2.zone.Zone._set_mode") as mock_fcn:
            await zone.async_set_temperature(temperature=19.1)

            assert mock_fcn.await_count == 1
            assert install != "default" or mock_fcn.await_args.args == (
                {
                    "setpointMode": "TemporaryOverride",
                    "HeatSetpointValue": 19.1,
                    "timeUntil": "2024-07-10T21:10:00Z",  # varies by install
                },
            )
            assert mock_fcn.await_args.kwargs == {}

            result.append(mock_fcn.await_args.args)

        with patch("evohomeasync2.zone.Zone._set_mode") as mock_fcn:
            await zone.async_set_temperature(
                temperature=19.2,
                until=dt_util.parse_datetime("2024-07-10T13:30:00Z"),
            )

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (
                {
                    "setpointMode": "TemporaryOverride",
                    "HeatSetpointValue": 19.2,
                    "timeUntil": "2024-07-10T13:30:00Z",
                },
            )
            assert mock_fcn.await_args.kwargs == {}

    assert result == snapshot
