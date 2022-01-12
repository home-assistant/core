"""deCONZ climate platform tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    FAN_ON,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
)
from homeassistant.components.deconz.climate import (
    DECONZ_FAN_SMART,
    DECONZ_PRESET_AUTO,
    DECONZ_PRESET_COMPLEX,
    DECONZ_PRESET_HOLIDAY,
    DECONZ_PRESET_MANUAL,
)
from homeassistant.components.deconz.const import CONF_ALLOW_CLIP_SENSOR
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_OFF,
    STATE_UNAVAILABLE,
)

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)


async def test_no_sensors(hass, aioclient_mock):
    """Test that no sensors in deconz results in no climate entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_simple_climate_device(hass, aioclient_mock, mock_deconz_websocket):
    """Test successful creation of climate entities.

    This is a simple water heater that only supports setting temperature and on and off.
    """
    data = {
        "sensors": {
            "0": {
                "config": {
                    "battery": 59,
                    "displayflipped": None,
                    "heatsetpoint": 2100,
                    "locked": True,
                    "mountingmode": None,
                    "offset": 0,
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "6130553ac247174809bae47144ee23f8",
                "lastseen": "2020-11-29T19:31Z",
                "manufacturername": "Danfoss",
                "modelid": "eTRV0100",
                "name": "thermostat",
                "state": {
                    "errorcode": None,
                    "lastupdated": "2020-11-29T19:28:40.665",
                    "mountingmodeactive": False,
                    "on": True,
                    "temperature": 2102,
                    "valve": 24,
                    "windowopen": "Closed",
                },
                "swversion": "01.02.0008 01.02",
                "type": "ZHAThermostat",
                "uniqueid": "14:b4:57:ff:fe:d5:4e:77-01-0201",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 2
    climate_thermostat = hass.states.get("climate.thermostat")
    assert climate_thermostat.state == HVAC_MODE_HEAT
    assert climate_thermostat.attributes["hvac_modes"] == [
        HVAC_MODE_HEAT,
        HVAC_MODE_OFF,
    ]
    assert climate_thermostat.attributes["current_temperature"] == 21.0
    assert climate_thermostat.attributes["temperature"] == 21.0
    assert climate_thermostat.attributes["locked"] is True
    assert hass.states.get("sensor.thermostat_battery_level").state == "59"

    # Event signals thermostat configured off

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"on": False},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == STATE_OFF

    # Event signals thermostat state on

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"on": True},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == HVAC_MODE_HEAT

    # Verify service calls

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/sensors/0/config")

    # Service turn on thermostat

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True}

    # Service turn on thermostat

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"on": False}

    # Service set HVAC mode to unsupported value

    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_AUTO},
            blocking=True,
        )


async def test_climate_device_without_cooling_support(
    hass, aioclient_mock, mock_deconz_websocket
):
    """Test successful creation of sensor entities."""
    data = {
        "sensors": {
            "1": {
                "name": "Thermostat",
                "type": "ZHAThermostat",
                "state": {"on": True, "temperature": 2260, "valve": 30},
                "config": {
                    "battery": 100,
                    "heatsetpoint": 2200,
                    "mode": "auto",
                    "offset": 10,
                    "reachable": True,
                },
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 2
    climate_thermostat = hass.states.get("climate.thermostat")
    assert climate_thermostat.state == HVAC_MODE_AUTO
    assert climate_thermostat.attributes["hvac_modes"] == [
        HVAC_MODE_AUTO,
        HVAC_MODE_HEAT,
        HVAC_MODE_OFF,
    ]
    assert climate_thermostat.attributes["current_temperature"] == 22.6
    assert climate_thermostat.attributes["temperature"] == 22.0
    assert hass.states.get("sensor.thermostat") is None
    assert hass.states.get("sensor.thermostat_battery_level").state == "100"
    assert hass.states.get("climate.presence_sensor") is None
    assert hass.states.get("climate.clip_thermostat") is None

    # Event signals thermostat configured off

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "config": {"mode": "off"},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == STATE_OFF

    # Event signals thermostat state on

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "config": {"mode": "other"},
        "state": {"on": True},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == HVAC_MODE_HEAT

    # Event signals thermostat state off

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"on": False},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == STATE_OFF

    # Verify service calls

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/sensors/1/config")

    # Service set HVAC mode to auto

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_AUTO},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"mode": "auto"}

    # Service set HVAC mode to heat

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"mode": "heat"}

    # Service set HVAC mode to off

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"mode": "off"}

    # Service set HVAC mode to unsupported value

    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_COOL},
            blocking=True,
        )

    # Service set temperature to 20

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.thermostat", ATTR_TEMPERATURE: 20},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[4][2] == {"heatsetpoint": 2000.0}

    # Service set temperature without providing temperature attribute

    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.thermostat",
                ATTR_TARGET_TEMP_HIGH: 30,
                ATTR_TARGET_TEMP_LOW: 10,
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(states) == 2
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_climate_device_with_cooling_support(
    hass, aioclient_mock, mock_deconz_websocket
):
    """Test successful creation of sensor entities."""
    data = {
        "sensors": {
            "0": {
                "config": {
                    "battery": 25,
                    "coolsetpoint": 1111,
                    "fanmode": None,
                    "heatsetpoint": 2222,
                    "mode": "heat",
                    "offset": 0,
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "074549903686a77a12ef0f06c499b1ef",
                "lastseen": "2020-11-27T13:45Z",
                "manufacturername": "Zen Within",
                "modelid": "Zen-01",
                "name": "Zen-01",
                "state": {
                    "lastupdated": "2020-11-27T13:42:40.863",
                    "on": False,
                    "temperature": 2320,
                },
                "type": "ZHAThermostat",
                "uniqueid": "00:24:46:00:00:11:6f:56-01-0201",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 2
    climate_thermostat = hass.states.get("climate.zen_01")
    assert climate_thermostat.state == HVAC_MODE_HEAT
    assert climate_thermostat.attributes["hvac_modes"] == [
        HVAC_MODE_AUTO,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_OFF,
    ]
    assert climate_thermostat.attributes["current_temperature"] == 23.2
    assert climate_thermostat.attributes["temperature"] == 22.2
    assert hass.states.get("sensor.zen_01_battery_level").state == "25"

    # Event signals thermostat state cool

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"mode": "cool"},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").state == HVAC_MODE_COOL
    assert hass.states.get("climate.zen_01").attributes["temperature"] == 11.1

    # Verify service calls

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/sensors/0/config")

    # Service set temperature to 20

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.zen_01", ATTR_TEMPERATURE: 20},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"coolsetpoint": 2000.0}


async def test_climate_device_with_fan_support(
    hass, aioclient_mock, mock_deconz_websocket
):
    """Test successful creation of sensor entities."""
    data = {
        "sensors": {
            "0": {
                "config": {
                    "battery": 25,
                    "coolsetpoint": None,
                    "fanmode": "auto",
                    "heatsetpoint": 2222,
                    "mode": "heat",
                    "offset": 0,
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "074549903686a77a12ef0f06c499b1ef",
                "lastseen": "2020-11-27T13:45Z",
                "manufacturername": "Zen Within",
                "modelid": "Zen-01",
                "name": "Zen-01",
                "state": {
                    "lastupdated": "2020-11-27T13:42:40.863",
                    "on": False,
                    "temperature": 2320,
                },
                "type": "ZHAThermostat",
                "uniqueid": "00:24:46:00:00:11:6f:56-01-0201",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 2
    climate_thermostat = hass.states.get("climate.zen_01")
    assert climate_thermostat.state == HVAC_MODE_HEAT
    assert climate_thermostat.attributes["fan_mode"] == FAN_AUTO
    assert climate_thermostat.attributes["fan_modes"] == [
        DECONZ_FAN_SMART,
        FAN_AUTO,
        FAN_HIGH,
        FAN_MEDIUM,
        FAN_LOW,
        FAN_ON,
        FAN_OFF,
    ]

    # Event signals fan mode defaults to off

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"fanmode": "unsupported"},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").attributes["fan_mode"] == FAN_OFF

    # Event signals unsupported fan mode

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"fanmode": "unsupported"},
        "state": {"on": True},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").attributes["fan_mode"] == FAN_ON

    # Event signals unsupported fan mode

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"fanmode": "unsupported"},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").attributes["fan_mode"] == FAN_ON

    # Verify service calls

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/sensors/0/config")

    # Service set fan mode to off

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.zen_01", ATTR_FAN_MODE: FAN_OFF},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"fanmode": "off"}

    # Service set fan mode to custom deCONZ mode smart

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.zen_01", ATTR_FAN_MODE: DECONZ_FAN_SMART},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"fanmode": "smart"}

    # Service set fan mode to unsupported value

    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.zen_01", ATTR_FAN_MODE: "unsupported"},
            blocking=True,
        )


async def test_climate_device_with_preset(hass, aioclient_mock, mock_deconz_websocket):
    """Test successful creation of sensor entities."""
    data = {
        "sensors": {
            "0": {
                "config": {
                    "battery": 25,
                    "coolsetpoint": None,
                    "fanmode": None,
                    "heatsetpoint": 2222,
                    "mode": "heat",
                    "preset": "auto",
                    "offset": 0,
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "074549903686a77a12ef0f06c499b1ef",
                "lastseen": "2020-11-27T13:45Z",
                "manufacturername": "Zen Within",
                "modelid": "Zen-01",
                "name": "Zen-01",
                "state": {
                    "lastupdated": "2020-11-27T13:42:40.863",
                    "on": False,
                    "temperature": 2320,
                },
                "type": "ZHAThermostat",
                "uniqueid": "00:24:46:00:00:11:6f:56-01-0201",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 2

    climate_zen_01 = hass.states.get("climate.zen_01")
    assert climate_zen_01.state == HVAC_MODE_HEAT
    assert climate_zen_01.attributes["current_temperature"] == 23.2
    assert climate_zen_01.attributes["temperature"] == 22.2
    assert climate_zen_01.attributes["preset_mode"] == DECONZ_PRESET_AUTO
    assert climate_zen_01.attributes["preset_modes"] == [
        DECONZ_PRESET_AUTO,
        PRESET_BOOST,
        PRESET_COMFORT,
        DECONZ_PRESET_COMPLEX,
        PRESET_ECO,
        DECONZ_PRESET_HOLIDAY,
        DECONZ_PRESET_MANUAL,
    ]

    # Event signals deCONZ preset

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"preset": "manual"},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert (
        hass.states.get("climate.zen_01").attributes["preset_mode"]
        == DECONZ_PRESET_MANUAL
    )

    # Event signals unknown preset

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"preset": "unsupported"},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").attributes["preset_mode"] is None

    # Verify service calls

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/sensors/0/config")

    # Service set preset to HASS preset

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.zen_01", ATTR_PRESET_MODE: PRESET_COMFORT},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"preset": "comfort"}

    # Service set preset to custom deCONZ preset

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.zen_01", ATTR_PRESET_MODE: DECONZ_PRESET_MANUAL},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"preset": "manual"}

    # Service set preset to unsupported value

    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: "climate.zen_01", ATTR_PRESET_MODE: "unsupported"},
            blocking=True,
        )


async def test_clip_climate_device(hass, aioclient_mock):
    """Test successful creation of sensor entities."""
    data = {
        "sensors": {
            "1": {
                "name": "Thermostat",
                "type": "ZHAThermostat",
                "state": {"on": True, "temperature": 2260, "valve": 30},
                "config": {
                    "battery": 100,
                    "heatsetpoint": 2200,
                    "mode": "auto",
                    "offset": 10,
                    "reachable": True,
                },
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "name": "CLIP thermostat",
                "type": "CLIPThermostat",
                "state": {"on": True, "temperature": 2260, "valve": 30},
                "config": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(
            hass, aioclient_mock, options={CONF_ALLOW_CLIP_SENSOR: True}
        )

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("climate.clip_thermostat").state == HVAC_MODE_HEAT

    # Disallow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: False}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert not hass.states.get("climate.clip_thermostat")

    # Allow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("climate.clip_thermostat").state == HVAC_MODE_HEAT


async def test_verify_state_update(hass, aioclient_mock, mock_deconz_websocket):
    """Test that state update properly."""
    data = {
        "sensors": {
            "1": {
                "name": "Thermostat",
                "type": "ZHAThermostat",
                "state": {"on": True, "temperature": 2260, "valve": 30},
                "config": {
                    "battery": 100,
                    "heatsetpoint": 2200,
                    "mode": "auto",
                    "offset": 10,
                    "reachable": True,
                },
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert hass.states.get("climate.thermostat").state == HVAC_MODE_AUTO

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"on": False},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == HVAC_MODE_AUTO


async def test_add_new_climate_device(hass, aioclient_mock, mock_deconz_websocket):
    """Test that adding a new climate device works."""
    event_added_sensor = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": {
            "id": "Thermostat id",
            "name": "Thermostat",
            "type": "ZHAThermostat",
            "state": {"on": True, "temperature": 2260, "valve": 30},
            "config": {
                "battery": 100,
                "heatsetpoint": 2200,
                "mode": "auto",
                "offset": 10,
                "reachable": True,
            },
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        },
    }

    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0

    await mock_deconz_websocket(data=event_added_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("climate.thermostat").state == HVAC_MODE_AUTO
    assert hass.states.get("sensor.thermostat_battery_level").state == "100"
