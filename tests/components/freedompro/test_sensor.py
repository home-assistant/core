"""Tests for the Freedompro sensor."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


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

    assert state.state == "0"

    with patch(
        "homeassistant.components.freedompro.get_states",
        return_value=[
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*2VAS3HTWINNZ5N6HVEIPDJ6NX85P2-AM-GSYWUCNPU0",
                "type": "leakSensor",
                "state": {"leakDetected": 0},
                "online": True,
            },
            {
                "uid": "2WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*2VAS3HTWINNZ5N6HVEIPDJ6NX85P2-AM-GSYWUCNPU0",
                "type": "lock",
                "state": {"lock": 0},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*ILYH1E3DWZOVMNEUIMDYMNLOW-LFRQFDPWWJOVHVDOS",
                "type": "fan",
                "state": {"on": False, "rotationSpeed": 0},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SOT3NKALCRQMHUHJUF79NUG6UQP1IIQIN1PJVRRPT0C",
                "type": "contactSensor",
                "state": {"contactSensorState": True},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*VTEPEDYE8DXGS8U94CJKQDLKMN6CUX1IJWSOER2HZCK",
                "type": "motionSensor",
                "state": {"motionDetected": False},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*QN-DDFMPEPRDOQV7W7JQG3NL0NPZGTLIBYT3HFSPNEY",
                "type": "humiditySensor",
                "state": {"currentRelativeHumidity": 1},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*1JKU1MVWHQL-Z9SCUS85VFXMRGNDCDNDDUVVDKBU31W",
                "type": "switch",
                "state": {"on": False},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*JHJZIZ9ORJNHB7DZNBNAOSEDECVTTZ48SABTCA3WA3M",
                "type": "lightbulb",
                "state": {"on": True, "brightness": 0, "saturation": 0, "hue": 0},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SNG7Y3R1R0S_W5BCNPP1O5WUN2NCEOOT27EFSYT6JYS",
                "type": "occupancySensor",
                "state": {"occupancyDetected": False},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*LWPVY7X1AX0DRWLYUUNZ3ZSTHMYNDDBQTPZCZQUUASA",
                "type": "temperatureSensor",
                "state": {"currentTemperature": 1},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*SXFMEXI4UMDBAMXXPI6LJV47O9NY-IRCAKZI7_MW0LY",
                "type": "smokeSensor",
                "state": {"smokeDetected": False},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*R6V0FNNF7SACWZ8V9NCOX7UCYI4ODSYAOJWZ80PLJ3C",
                "type": "carbonDioxideSensor",
                "state": {"carbonDioxideDetected": False, "carbonDioxideLevel": 0},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3-QURR5Q6ADA8ML1TBRG59RRGM1F9LVUZLKPYKFJQHC",
                "type": "lightbulb",
                "state": {"on": False},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*TWMYQKL3UVED4HSIIB9GXJWJZBQCXG-9VE-N2IUAIWI",
                "type": "thermostat",
                "state": {
                    "heatingCoolingState": 1,
                    "currentTemperature": 14,
                    "targetTemperature": 14,
                },
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS",
                "type": "windowCovering",
                "state": {"position": 0},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*JVRAR_6WVL1Y0PJ5GFWGPMFV7FLVD4MZKBWXC_UFWYM",
                "type": "lightSensor",
                "state": {"currentAmbientLightLevel": 1},
                "online": True,
            },
            {
                "uid": "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*0PUTVZVJJJL-ZHZZBHTIBS3-J-U7JYNPACFPJW0MD-I",
                "type": "outlet",
                "state": {"on": False},
                "online": True,
            },
        ],
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes.get("friendly_name") == name

        entry = registry.async_get(entity_id)
        assert entry
        assert entry.unique_id == uid

        assert state.state == "1"
