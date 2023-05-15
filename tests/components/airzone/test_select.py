"""The select tests for the Airzone platform."""

from unittest.mock import patch

from aioairzone.common import GrilleAngle, SleepTimeout
from aioairzone.const import (
    API_COLD_ANGLE,
    API_DATA,
    API_HEAT_ANGLE,
    API_SLEEP,
    API_SYSTEM_ID,
    API_ZONE_ID,
)
import pytest

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_airzone_create_selects(hass: HomeAssistant) -> None:
    """Test creation of selects."""

    await async_init_integration(hass)

    state = hass.states.get("select.despacho_cold_angle")
    assert state.state == str(GrilleAngle.DEG_90)

    state = hass.states.get("select.despacho_heat_angle")
    assert state.state == str(GrilleAngle.DEG_90)

    state = hass.states.get("select.despacho_sleep")
    assert state.state == str(SleepTimeout.SLEEP_OFF)

    state = hass.states.get("select.dorm_1_cold_angle")
    assert state.state == str(GrilleAngle.DEG_90)

    state = hass.states.get("select.dorm_1_heat_angle")
    assert state.state == str(GrilleAngle.DEG_90)

    state = hass.states.get("select.dorm_1_sleep")
    assert state.state == str(SleepTimeout.SLEEP_OFF)

    state = hass.states.get("select.dorm_2_cold_angle")
    assert state.state == str(GrilleAngle.DEG_90)

    state = hass.states.get("select.dorm_2_heat_angle")
    assert state.state == str(GrilleAngle.DEG_90)

    state = hass.states.get("select.dorm_2_sleep")
    assert state.state == str(SleepTimeout.SLEEP_OFF)

    state = hass.states.get("select.dorm_ppal_cold_angle")
    assert state.state == str(GrilleAngle.DEG_45)

    state = hass.states.get("select.dorm_ppal_heat_angle")
    assert state.state == str(GrilleAngle.DEG_50)

    state = hass.states.get("select.dorm_ppal_sleep")
    assert state.state == str(SleepTimeout.SLEEP_30)

    state = hass.states.get("select.salon_cold_angle")
    assert state.state == str(GrilleAngle.DEG_90)

    state = hass.states.get("select.salon_heat_angle")
    assert state.state == str(GrilleAngle.DEG_90)

    state = hass.states.get("select.salon_sleep")
    assert state.state == str(SleepTimeout.SLEEP_OFF)


async def test_airzone_select_sleep(hass: HomeAssistant) -> None:
    """Test select sleep."""

    await async_init_integration(hass)

    put_hvac_sleep = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 3,
                API_SLEEP: SleepTimeout.SLEEP_30.value,
            }
        ]
    }

    with pytest.raises(ValueError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dorm_1_sleep",
                ATTR_OPTION: "Invalid",
            },
            blocking=True,
        )

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_sleep,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dorm_1_sleep",
                ATTR_OPTION: str(SleepTimeout.SLEEP_30),
            },
            blocking=True,
        )

    state = hass.states.get("select.dorm_1_sleep")
    assert state.state == str(SleepTimeout.SLEEP_30)


async def test_airzone_select_grille_angle(hass: HomeAssistant) -> None:
    """Test select sleep."""

    await async_init_integration(hass)

    # Cold Angle

    put_hvac_cold_angle = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 3,
                API_COLD_ANGLE: GrilleAngle.DEG_50.value,
            }
        ]
    }

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_cold_angle,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dorm_1_cold_angle",
                ATTR_OPTION: str(GrilleAngle.DEG_50),
            },
            blocking=True,
        )

    state = hass.states.get("select.dorm_1_cold_angle")
    assert state.state == str(GrilleAngle.DEG_50)

    # Heat Angle

    put_hvac_heat_angle = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 3,
                API_HEAT_ANGLE: GrilleAngle.DEG_45.value,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_heat_angle,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.dorm_1_heat_angle",
                ATTR_OPTION: str(GrilleAngle.DEG_45),
            },
            blocking=True,
        )

    state = hass.states.get("select.dorm_1_heat_angle")
    assert state.state == str(GrilleAngle.DEG_45)
