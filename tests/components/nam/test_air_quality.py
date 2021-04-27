"""Test air_quality of Nettigo Air Monitor integration."""
from datetime import timedelta
from unittest.mock import patch

from nettigo_air_monitor import ApiError

from homeassistant.components.air_quality import ATTR_CO2, ATTR_PM_2_5, ATTR_PM_10
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import INCOMPLETE_NAM_DATA, NAM_DATA

from tests.common import async_fire_time_changed
from tests.components.nam import init_integration


async def test_air_quality(hass):
    """Test states of the air_quality."""
    await init_integration(hass)
    registry = er.async_get(hass)

    state = hass.states.get("air_quality.nettigo_air_monitor_sds011")
    assert state
    assert state.state == "11"
    assert state.attributes.get(ATTR_PM_10) == 19
    assert state.attributes.get(ATTR_PM_2_5) == 11
    assert state.attributes.get(ATTR_CO2) == 865
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get("air_quality.nettigo_air_monitor_sds011")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sds"

    state = hass.states.get("air_quality.nettigo_air_monitor_sps30")
    assert state
    assert state.state == "34"
    assert state.attributes.get(ATTR_PM_10) == 21
    assert state.attributes.get(ATTR_PM_2_5) == 34
    assert state.attributes.get(ATTR_CO2) == 865
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get("air_quality.nettigo_air_monitor_sps30")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sps30"


async def test_incompleta_data_after_device_restart(hass):
    """Test states of the air_quality after device restart."""
    await init_integration(hass)

    state = hass.states.get("air_quality.nettigo_air_monitor_sds011")
    assert state
    assert state.state == "11"
    assert state.attributes.get(ATTR_PM_10) == 19
    assert state.attributes.get(ATTR_PM_2_5) == 11
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    future = utcnow() + timedelta(minutes=6)
    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        return_value=INCOMPLETE_NAM_DATA,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("air_quality.nettigo_air_monitor_sds011")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_availability(hass):
    """Ensure that we mark the entities unavailable correctly when device causes an error."""
    await init_integration(hass)

    state = hass.states.get("air_quality.nettigo_air_monitor_sds011")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "11"

    future = utcnow() + timedelta(minutes=6)
    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("air_quality.nettigo_air_monitor_sds011")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=12)
    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        return_value=NAM_DATA,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("air_quality.nettigo_air_monitor_sds011")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "11"


async def test_manual_update_entity(hass):
    """Test manual update entity via service homeasasistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})

    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        return_value=NAM_DATA,
    ) as mock_get_data:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["air_quality.nettigo_air_monitor_sds011"]},
            blocking=True,
        )

    assert mock_get_data.call_count == 1
