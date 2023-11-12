"""Tests for the Freedompro sensor."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import get_states_response_for_uid

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    ("entity_id", "uid", "name"),
    [
        (
            "sensor.garden_humidity_sensor",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*QN-DDFMPEPRDOQV7W7JQG3NL0NPZGTLIBYT3HFSPNEY",
            "Garden humidity sensor",
        ),
        (
            "sensor.living_room_temperature_sensor",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*LWPVY7X1AX0DRWLYUUNZ3ZSTHMYNDDBQTPZCZQUUASA",
            "Living room temperature sensor",
        ),
        (
            "sensor.garden_light_sensors",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*JVRAR_6WVL1Y0PJ5GFWGPMFV7FLVD4MZKBWXC_UFWYM",
            "Garden light sensors",
        ),
    ],
)
async def test_sensor_get_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration,
    entity_id: str,
    uid: str,
    name: str,
) -> None:
    """Test states of the sensor."""
    init_integration

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("friendly_name") == name

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid

    assert state.state == "0"

    states_response = get_states_response_for_uid(uid)
    if states_response[0]["type"] == "lightSensor":
        states_response[0]["state"]["currentAmbientLightLevel"] = "1"
    elif states_response[0]["type"] == "temperatureSensor":
        states_response[0]["state"]["currentTemperature"] = "1"
    elif states_response[0]["type"] == "humiditySensor":
        states_response[0]["state"]["currentRelativeHumidity"] = "1"
    with patch(
        "homeassistant.components.freedompro.coordinator.get_states",
        return_value=states_response,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes.get("friendly_name") == name

        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.unique_id == uid

        assert state.state == "1"
