"""Test Z-Wave Multi-setpoint Climate entities."""
from homeassistant.components.climate import ATTR_TEMPERATURE
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)

from .common import setup_ozw


async def test_climate(hass, climate_data, sent_messages, climate_msg, caplog):
    """Test setting up config entry."""
    receive_message = await setup_ozw(hass, fixture=climate_data)

    # Test multi-setpoint thermostat (node 7 in dump)
    # mode is heat, this should be single setpoint
    state = hass.states.get("climate.ct32_thermostat_mode")
    assert state is not None
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_OFF,
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_AUTO,
    ]
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 23.1
    assert state.attributes[ATTR_TEMPERATURE] == 21.1
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) is None
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) is None
    assert state.attributes[ATTR_FAN_MODE] == "Auto Low"
    assert state.attributes[ATTR_FAN_MODES] == ["Auto Low", "On Low"]

    # Test set target temperature
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.ct32_thermostat_mode", "temperature": 26.1},
        blocking=True,
    )
    assert len(sent_messages) == 1
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    # Celsius is converted to Fahrenheit here!
    assert round(msg["payload"]["Value"], 2) == 78.98
    assert msg["payload"]["ValueIDKey"] == 281475099443218

    # Test set mode
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.ct32_thermostat_mode", "hvac_mode": HVAC_MODE_AUTO},
        blocking=True,
    )
    assert len(sent_messages) == 2
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 3, "ValueIDKey": 122683412}

    # Test set missing mode
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.ct32_thermostat_mode", "hvac_mode": "fan_only"},
        blocking=True,
    )
    assert len(sent_messages) == 2
    assert "Received an invalid hvac mode: fan_only" in caplog.text

    # Test set fan mode
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.ct32_thermostat_mode", "fan_mode": "On Low"},
        blocking=True,
    )
    assert len(sent_messages) == 3
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 1, "ValueIDKey": 122748948}

    # Test set invalid fan mode
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.ct32_thermostat_mode", "fan_mode": "invalid fan mode"},
        blocking=True,
    )
    assert len(sent_messages) == 3
    assert "Received an invalid fan mode: invalid fan mode" in caplog.text

    # Test incoming mode change to auto,
    # resulting in multiple setpoints
    receive_message(climate_msg)
    await hass.async_block_till_done()
    state = hass.states.get("climate.ct32_thermostat_mode")
    assert state is not None
    assert state.state == HVAC_MODE_AUTO
    assert state.attributes.get(ATTR_TEMPERATURE) is None
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 21.1
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 25.6

    # Test setting high/low temp on multiple setpoints
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.ct32_thermostat_mode",
            "target_temp_low": 20,
            "target_temp_high": 25,
        },
        blocking=True,
    )
    assert len(sent_messages) == 5  # 2 messages !
    msg = sent_messages[-2]  # low setpoint
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert round(msg["payload"]["Value"], 2) == 68.0
    assert msg["payload"]["ValueIDKey"] == 281475099443218
    msg = sent_messages[-1]  # high setpoint
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert round(msg["payload"]["Value"], 2) == 77.0
    assert msg["payload"]["ValueIDKey"] == 562950076153874

    # Test basic/single-setpoint thermostat (node 16 in dump)
    state = hass.states.get("climate.komforthaus_spirit_z_wave_plus_mode")
    assert state is not None
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_OFF,
        HVAC_MODE_HEAT,
    ]
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 17.3
    assert round(state.attributes[ATTR_TEMPERATURE], 0) == 19
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) is None
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) is None
    assert state.attributes[ATTR_PRESET_MODES] == [
        "none",
        "Heat Eco",
        "Full Power",
        "Manufacturer Specific",
    ]

    # Test set target temperature
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.komforthaus_spirit_z_wave_plus_mode",
            "temperature": 28.0,
        },
        blocking=True,
    )
    assert len(sent_messages) == 6
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": 28.0,
        "ValueIDKey": 281475250438162,
    }

    # Test set preset mode
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": "climate.komforthaus_spirit_z_wave_plus_mode",
            "preset_mode": "Heat Eco",
        },
        blocking=True,
    )
    assert len(sent_messages) == 7
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": 11,
        "ValueIDKey": 273678356,
    }

    # Test set preset mode None
    # This preset should set and return to current hvac mode
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": "climate.komforthaus_spirit_z_wave_plus_mode",
            "preset_mode": "none",
        },
        blocking=True,
    )
    assert len(sent_messages) == 8
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": 1,
        "ValueIDKey": 273678356,
    }

    # Test set invalid preset mode
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": "climate.komforthaus_spirit_z_wave_plus_mode",
            "preset_mode": "invalid preset mode",
        },
        blocking=True,
    )
    assert len(sent_messages) == 8
    assert "Received an invalid preset mode: invalid preset mode" in caplog.text
