"""Test Alexa handlers helper methods."""

from unittest.mock import Mock

import pytest

from homeassistant.components import (
    cover,
    fan,
    humidifier,
    input_number,
    number,
    remote,
    vacuum,
    valve,
    water_heater,
)
from homeassistant.components.alexa.const import PRESET_MODE_NA
from homeassistant.components.alexa.errors import AlexaInvalidValueError
from homeassistant.components.alexa.handlers import (
    _adjust_cover_position,
    _adjust_cover_tilt,
    _adjust_fan_percentage,
    _adjust_humidifier_humidity,
    _adjust_input_number,
    _adjust_number,
    _adjust_vacuum_fan_speed,
    _adjust_valve_position,
    _alexa_cover_position_handler,
    _alexa_cover_tilt_handler,
    _alexa_fan_percentage_handler,
    _alexa_humidifier_humidity_handler,
    _alexa_input_number_value_handler,
    _alexa_number_value_handler,
    _alexa_vacuum_fan_speed_handler,
    _alexa_valve_position_handler,
    _cover_position,
    _fan_direction,
    _fan_preset_mode,
    _humidifier_mode,
    _remote_activity,
    _valve_position_state,
    _water_heater_operation_mode,
)
from homeassistant.const import ATTR_ENTITY_ID


def test_mode_controller_helper_methods():
    """Test mode controller helper methods."""
    # Create mock entity
    entity = Mock()
    entity.entity_id = "test.entity"

    # Test _fan_direction
    service, data = _fan_direction(entity, "Direction.forward")
    assert service == fan.SERVICE_SET_DIRECTION
    assert data == {ATTR_ENTITY_ID: "test.entity", fan.ATTR_DIRECTION: "forward"}

    service, data = _fan_direction(entity, "Direction.reverse")
    assert service == fan.SERVICE_SET_DIRECTION
    assert data == {ATTR_ENTITY_ID: "test.entity", fan.ATTR_DIRECTION: "reverse"}

    # Test invalid direction
    with pytest.raises(AlexaInvalidValueError):
        _fan_direction(entity, "Direction.Invalid")

    # Test _fan_preset_mode
    entity.attributes = {fan.ATTR_PRESET_MODES: ["auto", "sleep"]}
    service, data = _fan_preset_mode(entity, "PresetMode.auto")
    assert service == fan.SERVICE_SET_PRESET_MODE
    assert data == {ATTR_ENTITY_ID: "test.entity", fan.ATTR_PRESET_MODE: "auto"}

    # Test NA preset mode
    with pytest.raises(AlexaInvalidValueError):
        _fan_preset_mode(entity, f"PresetMode.{PRESET_MODE_NA}")

    # Test _humidifier_mode
    entity.attributes = {humidifier.ATTR_AVAILABLE_MODES: ["normal", "eco"]}
    service, data = _humidifier_mode(entity, "Mode.normal")
    assert service == humidifier.SERVICE_SET_MODE
    assert data == {ATTR_ENTITY_ID: "test.entity", humidifier.ATTR_MODE: "normal"}

    # Test _remote_activity
    entity.attributes = {remote.ATTR_ACTIVITY_LIST: ["Watch TV", "Listen Music"]}
    service, data = _remote_activity(entity, "Activity.Watch TV")
    assert service == remote.SERVICE_TURN_ON
    assert data == {ATTR_ENTITY_ID: "test.entity", remote.ATTR_ACTIVITY: "Watch TV"}

    # Test _water_heater_operation_mode
    entity.attributes = {water_heater.ATTR_OPERATION_LIST: ["eco", "heat_pump"]}
    service, data = _water_heater_operation_mode(entity, "OperationMode.eco")
    assert service == water_heater.SERVICE_SET_OPERATION_MODE
    assert data == {
        ATTR_ENTITY_ID: "test.entity",
        water_heater.ATTR_OPERATION_MODE: "eco",
    }

    # Test _cover_position
    service, data = _cover_position(entity, "Position.closed")
    assert service == cover.SERVICE_CLOSE_COVER
    assert data == {ATTR_ENTITY_ID: "test.entity"}

    service, data = _cover_position(entity, "Position.open")
    assert service == cover.SERVICE_OPEN_COVER
    assert data == {ATTR_ENTITY_ID: "test.entity"}

    service, data = _cover_position(entity, "Position.custom")
    assert service == cover.SERVICE_STOP_COVER
    assert data == {ATTR_ENTITY_ID: "test.entity"}

    # Test _valve_position_state
    service, data = _valve_position_state(entity, "State.closed")
    assert service == valve.SERVICE_CLOSE_VALVE
    assert data == {ATTR_ENTITY_ID: "test.entity"}

    service, data = _valve_position_state(entity, "State.open")
    assert service == valve.SERVICE_OPEN_VALVE
    assert data == {ATTR_ENTITY_ID: "test.entity"}


def test_range_controller_handler_methods():
    """Test range controller handler methods."""
    entity = Mock()
    entity.entity_id = "test.entity"

    # Test _alexa_cover_position_handler
    supported = cover.CoverEntityFeature.SET_POSITION
    service, data = _alexa_cover_position_handler(entity, 50, supported)
    assert service == cover.SERVICE_SET_COVER_POSITION
    assert data == {ATTR_ENTITY_ID: "test.entity", cover.ATTR_POSITION: 50}

    # Test close cover (0%)
    supported = cover.CoverEntityFeature.CLOSE
    service, data = _alexa_cover_position_handler(entity, 0, supported)
    assert service == cover.SERVICE_CLOSE_COVER
    assert data == {ATTR_ENTITY_ID: "test.entity"}

    # Test open cover (100%)
    supported = cover.CoverEntityFeature.OPEN
    service, data = _alexa_cover_position_handler(entity, 100, supported)
    assert service == cover.SERVICE_OPEN_COVER
    assert data == {ATTR_ENTITY_ID: "test.entity"}

    # Test _alexa_cover_tilt_handler
    supported = cover.CoverEntityFeature.SET_TILT_POSITION
    service, data = _alexa_cover_tilt_handler(entity, 75, supported)
    assert service == cover.SERVICE_SET_COVER_TILT_POSITION
    assert data == {ATTR_ENTITY_ID: "test.entity", cover.ATTR_TILT_POSITION: 75}

    # Test _alexa_fan_percentage_handler
    supported = fan.FanEntityFeature.SET_SPEED
    service, data = _alexa_fan_percentage_handler(entity, 60, supported)
    assert service == fan.SERVICE_SET_PERCENTAGE
    assert data == {ATTR_ENTITY_ID: "test.entity", fan.ATTR_PERCENTAGE: 60}

    # Test fan turn off (0%)
    service, data = _alexa_fan_percentage_handler(entity, 0, supported)
    assert service == fan.SERVICE_TURN_OFF
    assert data == {ATTR_ENTITY_ID: "test.entity"}

    # Test _alexa_humidifier_humidity_handler
    service, data = _alexa_humidifier_humidity_handler(entity, 45, 0)
    assert service == humidifier.SERVICE_SET_HUMIDITY
    assert data == {ATTR_ENTITY_ID: "test.entity", humidifier.ATTR_HUMIDITY: 45}

    # Test _alexa_input_number_value_handler
    entity.attributes = {input_number.ATTR_MIN: 0, input_number.ATTR_MAX: 100}
    service, data = _alexa_input_number_value_handler(entity, 25, 0)
    assert service == input_number.SERVICE_SET_VALUE
    assert data == {ATTR_ENTITY_ID: "test.entity", input_number.ATTR_VALUE: 25}

    # Test value clamping
    service, data = _alexa_input_number_value_handler(entity, 150, 0)
    assert data[input_number.ATTR_VALUE] == 100  # Clamped to max

    # Test _alexa_number_value_handler
    entity.attributes = {number.ATTR_MIN: 10, number.ATTR_MAX: 90}
    service, data = _alexa_number_value_handler(entity, 55, 0)
    assert service == number.SERVICE_SET_VALUE
    assert data == {ATTR_ENTITY_ID: "test.entity", number.ATTR_VALUE: 55}

    # Test _alexa_vacuum_fan_speed_handler
    entity.attributes = {vacuum.ATTR_FAN_SPEED_LIST: ["low", "medium", "high"]}
    service, data = _alexa_vacuum_fan_speed_handler(entity, 1, 0)
    assert service == vacuum.SERVICE_SET_FAN_SPEED
    assert data == {ATTR_ENTITY_ID: "test.entity", vacuum.ATTR_FAN_SPEED: "medium"}

    # Test invalid speed index
    with pytest.raises(AlexaInvalidValueError):
        _alexa_vacuum_fan_speed_handler(entity, 5, 0)

    # Test _alexa_valve_position_handler
    supported = valve.ValveEntityFeature.SET_POSITION
    service, data = _alexa_valve_position_handler(entity, 30, supported)
    assert service == valve.SERVICE_SET_VALVE_POSITION
    assert data == {ATTR_ENTITY_ID: "test.entity", valve.ATTR_POSITION: 30}


def test_adjust_range_helper_methods():
    """Test adjust range helper methods."""
    entity = Mock()
    entity.entity_id = "test.entity"

    # Test _adjust_cover_position
    entity.attributes = {cover.ATTR_CURRENT_POSITION: 50}
    service, data, position = _adjust_cover_position(entity, 20, False)
    assert service == cover.SERVICE_SET_COVER_POSITION
    assert data == {ATTR_ENTITY_ID: "test.entity", cover.ATTR_POSITION: 70}
    assert position == 70

    # Test adjust to 100% (open)
    entity.attributes = {cover.ATTR_CURRENT_POSITION: 80}
    service, data, position = _adjust_cover_position(entity, 20, False)
    assert service == cover.SERVICE_OPEN_COVER
    assert position == 100

    # Test adjust to 0% (close)
    entity.attributes = {cover.ATTR_CURRENT_POSITION: 10}
    service, data, position = _adjust_cover_position(entity, -20, False)
    assert service == cover.SERVICE_CLOSE_COVER
    assert position == 0

    # Test missing current position
    entity.attributes = {}
    with pytest.raises(AlexaInvalidValueError):
        _adjust_cover_position(entity, 10, False)

    # Test _adjust_cover_tilt
    entity.attributes = {cover.ATTR_TILT_POSITION: 40}
    service, data, tilt_position = _adjust_cover_tilt(entity, 30, False)
    assert service == cover.SERVICE_SET_COVER_TILT_POSITION
    assert data == {ATTR_ENTITY_ID: "test.entity", cover.ATTR_TILT_POSITION: 70}
    assert tilt_position == 70

    # Test _adjust_fan_percentage
    entity.attributes = {fan.ATTR_PERCENTAGE: 60, fan.ATTR_PERCENTAGE_STEP: 10}
    service, data, percentage = _adjust_fan_percentage(entity, 20, False)
    assert service == fan.SERVICE_SET_PERCENTAGE
    assert data == {ATTR_ENTITY_ID: "test.entity", fan.ATTR_PERCENTAGE: 80}
    assert percentage == 80

    # Test adjust to 0% (turn off)
    entity.attributes = {fan.ATTR_PERCENTAGE: 10}
    service, data, percentage = _adjust_fan_percentage(entity, -20, False)
    assert service == fan.SERVICE_TURN_OFF
    assert percentage == 0

    # Test _adjust_humidifier_humidity
    entity.attributes = {
        humidifier.ATTR_HUMIDITY: 50,
        humidifier.ATTR_MIN_HUMIDITY: 30,
        humidifier.ATTR_MAX_HUMIDITY: 80,
    }
    service, data, humidity = _adjust_humidifier_humidity(entity, 15, False)
    assert service == humidifier.SERVICE_SET_HUMIDITY
    assert data == {ATTR_ENTITY_ID: "test.entity", humidifier.ATTR_HUMIDITY: 65}
    assert humidity == 65

    # Test _adjust_input_number
    entity.state = "25.5"
    entity.attributes = {input_number.ATTR_MIN: 0, input_number.ATTR_MAX: 100}
    service, data, value = _adjust_input_number(entity, 10.5, False)
    assert service == input_number.SERVICE_SET_VALUE
    assert data == {ATTR_ENTITY_ID: "test.entity", input_number.ATTR_VALUE: 36.0}
    assert value == 36.0

    # Test _adjust_number
    entity.state = "42.3"
    entity.attributes = {number.ATTR_MIN: 0, number.ATTR_MAX: 100}
    service, data, value = _adjust_number(entity, -12.3, False)
    assert service == number.SERVICE_SET_VALUE
    assert data[ATTR_ENTITY_ID] == "test.entity"
    assert (
        abs(data[number.ATTR_VALUE] - 30.0) < 0.001
    )  # Account for floating point precision
    assert abs(value - 30.0) < 0.001

    # Test _adjust_vacuum_fan_speed
    entity.attributes = {
        vacuum.ATTR_FAN_SPEED_LIST: ["quiet", "standard", "medium", "high"],
        vacuum.ATTR_FAN_SPEED: "standard",
    }
    service, data, speed = _adjust_vacuum_fan_speed(entity, 2, False)
    assert service == vacuum.SERVICE_SET_FAN_SPEED
    assert data == {ATTR_ENTITY_ID: "test.entity", vacuum.ATTR_FAN_SPEED: "high"}
    assert speed == "high"

    # Test _adjust_valve_position
    entity.attributes = {valve.ATTR_POSITION: 40}
    service, data, position = _adjust_valve_position(entity, 35, False)
    assert service == valve.SERVICE_SET_VALVE_POSITION
    assert data == {ATTR_ENTITY_ID: "test.entity", valve.ATTR_POSITION: 75}
    assert position == 75
