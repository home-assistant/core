"""The tests for water_heater entities of evohome.

Not all evohome systems will have a DHW zone.
"""

from __future__ import annotations

from unittest.mock import patch

from evohomeasync2 import EvohomeClient
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

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
from homeassistant.exceptions import HomeAssistantError

from .const import TEST_INSTALLS_WITH_DHW

DHW_ENTITY_ID = "water_heater.domestic_hot_water"


@pytest.mark.parametrize("install", TEST_INSTALLS_WITH_DHW)
async def test_set_operation_mode(
    hass: HomeAssistant,
    evohome: EvohomeClient,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test SERVICE_SET_OPERATION_MODE of a evohome HotWater entity."""

    freezer.move_to("2024-07-10T11:55:00Z")
    results = []

    # SERVICE_SET_OPERATION_MODE: auto
    with patch("evohomeasync2.hotwater.HotWater.reset_mode") as mock_fcn:
        await hass.services.async_call(
            Platform.WATER_HEATER,
            SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: DHW_ENTITY_ID,
                ATTR_OPERATION_MODE: "auto",
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == ()
        assert mock_fcn.await_args.kwargs == {}

    # SERVICE_SET_OPERATION_MODE: off (until next scheduled setpoint)
    with patch("evohomeasync2.hotwater.HotWater.set_off") as mock_fcn:
        await hass.services.async_call(
            Platform.WATER_HEATER,
            SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: DHW_ENTITY_ID,
                ATTR_OPERATION_MODE: "off",
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == ()
        results.append(mock_fcn.await_args.args)

    # SERVICE_SET_OPERATION_MODE: on (until next scheduled setpoint)
    with patch("evohomeasync2.hotwater.HotWater.set_on") as mock_fcn:
        await hass.services.async_call(
            Platform.WATER_HEATER,
            SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: DHW_ENTITY_ID,
                ATTR_OPERATION_MODE: "on",
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == ()
        results.append(mock_fcn.await_args.args)

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS_WITH_DHW)
async def test_set_away_mode(hass: HomeAssistant, evohome: EvohomeClient) -> None:
    """Test SERVICE_SET_AWAY_MODE of a evohome HotWater entity."""

    # set_away_mode: off
    with patch("evohomeasync2.hotwater.HotWater.reset_mode") as mock_fcn:
        await hass.services.async_call(
            Platform.WATER_HEATER,
            SERVICE_SET_AWAY_MODE,
            {
                ATTR_ENTITY_ID: DHW_ENTITY_ID,
                ATTR_AWAY_MODE: "off",
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == ()
        assert mock_fcn.await_args.kwargs == {}

    # set_away_mode: off
    with patch("evohomeasync2.hotwater.HotWater.set_off") as mock_fcn:
        await hass.services.async_call(
            Platform.WATER_HEATER,
            SERVICE_SET_AWAY_MODE,
            {
                ATTR_ENTITY_ID: DHW_ENTITY_ID,
                ATTR_AWAY_MODE: "on",
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == ()
        assert mock_fcn.await_args.kwargs == {}


@pytest.mark.parametrize("install", TEST_INSTALLS_WITH_DHW)
async def test_turn_off(hass: HomeAssistant, evohome: EvohomeClient) -> None:
    """Test SERVICE_TURN_OFF of a evohome HotWater entity."""

    # Entity water_heater.domestic_hot_water does not support this service
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.WATER_HEATER,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: DHW_ENTITY_ID,
            },
            blocking=True,
        )


@pytest.mark.parametrize("install", TEST_INSTALLS_WITH_DHW)
async def test_turn_on(hass: HomeAssistant, evohome: EvohomeClient) -> None:
    """Test SERVICE_TURN_ON of a evohome HotWater entity."""

    # Entity water_heater.domestic_hot_water does not support this service
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.WATER_HEATER,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: DHW_ENTITY_ID,
            },
            blocking=True,
        )
