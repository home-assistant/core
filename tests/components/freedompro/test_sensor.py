"""Tests for the Freedompro sensor."""
import pytest

from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    "entity_id, uid, name",
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
    hass, init_integration, entity_id: str, uid: str, name: str
):
    """Test states of the sensor."""
    init_integration
    registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("friendly_name") == name

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid
