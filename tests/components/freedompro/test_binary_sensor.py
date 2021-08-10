"""Tests for the Freedompro binary sensor."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.components.freedompro.const import DEVICES_STATE


@pytest.mark.parametrize(
    "entity_id, uid, name, model",
    [
        (
            "binary_sensor.doorway_motion_sensor",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*VTEPEDYE8DXGS8U94CJKQDLKMN6CUX1IJWSOER2HZCK",
            "Doorway motion sensor",
            "motionSensor",
        ),
        (
            "binary_sensor.contact_sensor_living_room",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SOT3NKALCRQMHUHJUF79NUG6UQP1IIQIN1PJVRRPT0C",
            "Contact sensor living room",
            "contactSensor",
        ),
        (
            "binary_sensor.living_room_occupancy_sensor",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SNG7Y3R1R0S_W5BCNPP1O5WUN2NCEOOT27EFSYT6JYS",
            "Living room occupancy sensor",
            "occupancySensor",
        ),
        (
            "binary_sensor.smoke_sensor_kitchen",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SXFMEXI4UMDBAMXXPI6LJV47O9NY-IRCAKZI7_MW0LY",
            "Smoke sensor kitchen",
            "smokeSensor",
        ),
    ],
)
async def test_binary_sensor_get_state(
    hass, init_integration, entity_id: str, uid: str, name: str, model: str
):
    """Test states of the binary_sensor."""
    init_integration
    registry = er.async_get(hass)
    registry_device = dr.async_get(hass)

    device = registry_device.async_get_device({("freedompro", uid)})
    assert device is not None
    assert device.identifiers == {("freedompro", uid)}
    assert device.manufacturer == "Freedompro"
    assert device.name == name
    assert device.model == model

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("friendly_name") == name

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid

    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.freedompro.get_states",
        return_value=[],
    ):

        async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes.get("friendly_name") == name

        entry = registry.async_get(entity_id)
        assert entry
        assert entry.unique_id == uid

        assert state.state == STATE_OFF

    get_states_response = list(DEVICES_STATE)
    for state_response in get_states_response:
        if state_response["uid"] == uid:
            if state_response["type"] == "smokeSensor":
                state_response["state"]["smokeDetected"] = True
            if state_response["type"] == "occupancySensor":
                state_response["state"]["occupancyDetected"] = True
            if state_response["type"] == "motionSensor":
                state_response["state"]["motionDetected"] = True
            if state_response["type"] == "contactSensor":
                state_response["state"]["contactSensorState"] = True
    with patch(
        "homeassistant.components.freedompro.get_states",
        return_value=get_states_response,
    ):

        async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes.get("friendly_name") == name

        entry = registry.async_get(entity_id)
        assert entry
        assert entry.unique_id == uid

        assert state.state == STATE_ON
