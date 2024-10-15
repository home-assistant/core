"""The tests for water_heater entities of evohome.

Not all evohome systems will have a DHW zone.
"""

from __future__ import annotations

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.evohome import DOMAIN
from homeassistant.components.evohome.coordinator import EvoBroker
from homeassistant.components.evohome.water_heater import EvoDHW
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent

from .conftest import setup_evohome
from .const import TEST_INSTALLS_WITH_DHW


def get_dhw_entity(hass: HomeAssistant) -> EvoDHW | None:
    """Return the DHW entity of the evohome system."""

    broker: EvoBroker = hass.data[DOMAIN]["broker"]

    if (dhw := broker.tcs.hotwater) is None:
        return None

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        Platform.WATER_HEATER, DOMAIN, dhw._id
    )

    component: EntityComponent = hass.data.get(Platform.WATER_HEATER)  # type: ignore[assignment]
    return next(e for e in component.entities if e.entity_id == entity_id)  # type: ignore[return-value]


@pytest.mark.parametrize("install", TEST_INSTALLS_WITH_DHW)
async def test_set_operation_mode(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test water_heater services of a evohome-compatible DHW zone."""

    freezer.move_to("2024-07-10T11:55:00Z")
    results = []

    async for _ in setup_evohome(hass, config, install=install):
        dhw = get_dhw_entity(hass)

        # set_operation_mode(auto): FollowSchedule
        with patch("evohomeasync2.hotwater.HotWater._set_mode") as mock_fcn:
            await dhw.async_set_operation_mode("auto")

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (
                {
                    "mode": "FollowSchedule",
                    "state": None,
                    "untilTime": None,
                },
            )
            assert mock_fcn.await_args.kwargs == {}

        # set_operation_mode(off): TemporaryOverride, advanced
        with patch("evohomeasync2.hotwater.HotWater._set_mode") as mock_fcn:
            await dhw.async_set_operation_mode("off")

            assert mock_fcn.await_count == 1
            assert install != "default" or mock_fcn.await_args.args == (
                {
                    "mode": "TemporaryOverride",
                    "state": "Off",
                    "untilTime": "2024-07-10T12:00:00Z",  # varies by install
                },
            )
            assert mock_fcn.await_args.kwargs == {}

            results.append(mock_fcn.await_args.args)

        # set_operation_mode(on): TemporaryOverride, advanced
        with patch("evohomeasync2.hotwater.HotWater._set_mode") as mock_fcn:
            await dhw.async_set_operation_mode("on")

            assert mock_fcn.await_count == 1
            assert install != "default" or mock_fcn.await_args.args == (
                {
                    "mode": "TemporaryOverride",
                    "state": "On",
                    "untilTime": "2024-07-10T12:00:00Z",  # varies by install
                },
            )
            assert mock_fcn.await_args.kwargs == {}

            results.append(mock_fcn.await_args.args)

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS_WITH_DHW)
async def test_turn_away_mode_off(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
) -> None:
    """Test water_heater services of a evohome-compatible DHW zone."""

    async for _ in setup_evohome(hass, config, install=install):
        dhw = get_dhw_entity(hass)

        # turn_away_mode_off(): FollowSchedule
        with patch("evohomeasync2.hotwater.HotWater._set_mode") as mock_fcn:
            await dhw.async_turn_away_mode_off()

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (
                {
                    "mode": "FollowSchedule",
                    "state": None,
                    "untilTime": None,
                },
            )
            assert mock_fcn.await_args.kwargs == {}


@pytest.mark.parametrize("install", TEST_INSTALLS_WITH_DHW)
async def test_turn_away_mode_on(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
) -> None:
    """Test water_heater services of a evohome-compatible DHW zone."""

    async for _ in setup_evohome(hass, config, install=install):
        dhw = get_dhw_entity(hass)

        # turn_away_mode_on(): PermanentOverride, Off
        with patch("evohomeasync2.hotwater.HotWater._set_mode") as mock_fcn:
            await dhw.async_turn_away_mode_on()

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (
                {
                    "mode": "PermanentOverride",
                    "state": "Off",
                    "untilTime": None,
                },
            )
            assert mock_fcn.await_args.kwargs == {}


@pytest.mark.parametrize("install", TEST_INSTALLS_WITH_DHW)
async def test_turn_off(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
) -> None:
    """Test water_heater services of a evohome-compatible DHW zone."""

    async for _ in setup_evohome(hass, config, install=install):
        dhw = get_dhw_entity(hass)

        # turn_off(): PermanentOverride, Off
        with patch("evohomeasync2.hotwater.HotWater._set_mode") as mock_fcn:
            await dhw.async_turn_off()

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (
                {
                    "mode": "PermanentOverride",
                    "state": "Off",
                    "untilTime": None,
                },
            )
            assert mock_fcn.await_args.kwargs == {}


@pytest.mark.parametrize("install", TEST_INSTALLS_WITH_DHW)
async def test_turn_on(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
) -> None:
    """Test water_heater services of a evohome-compatible DHW zone."""

    async for _ in setup_evohome(hass, config, install=install):
        dhw = get_dhw_entity(hass)

        # turn_on(): PermanentOverride, On
        with patch("evohomeasync2.hotwater.HotWater._set_mode") as mock_fcn:
            await dhw.async_turn_on()

            assert mock_fcn.await_count == 1
            assert mock_fcn.await_args.args == (
                {
                    "mode": "PermanentOverride",
                    "state": "On",
                    "untilTime": None,
                },
            )
            assert mock_fcn.await_args.kwargs == {}
