"""Sensor tests for the Google Mail integration."""
from datetime import timedelta
from unittest.mock import patch

from google.auth.exceptions import RefreshError
from httplib2 import Response

from homeassistant import config_entries
from homeassistant.components.google_mail.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .conftest import SENSOR, TOKEN, ComponentSetup

from tests.common import async_fire_time_changed, load_fixture


async def test_sensors(hass: HomeAssistant, setup_integration: ComponentSetup) -> None:
    """Test we get sensor data."""
    await setup_integration()

    state = hass.states.get(SENSOR)
    assert state.state == "2022-11-18T05:00:00+00:00"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP

    with patch(
        "httplib2.Http.request",
        return_value=(
            Response({}),
            bytes(load_fixture("google_mail/get_vacation_off.json"), encoding="UTF-8"),
        ),
    ):
        next_update = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR)
    assert state.state == STATE_UNKNOWN


async def test_sensor_reauth_trigger(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test reauth is triggered after a refresh error."""
    await setup_integration()

    with patch(TOKEN, side_effect=RefreshError):
        next_update = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
