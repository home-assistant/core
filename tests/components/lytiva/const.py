"""Constants for Lytiva integration tests."""

# Mock MQTT discovery payloads
MOCK_LIGHT_DISCOVERY = {
    "name": "Test Light",
    "unique_id": "lytiva_light_1",
    "address": 1,
    "state_topic": "LYT/1/NODE/E/STATUS",
    "command_topic": "LYT/1/NODE/E/COMMAND",
    "brightness_state_topic": "LYT/1/NODE/E/STATUS",
    "brightness_command_topic": "LYT/1/NODE/E/COMMAND",
    "device": {
        "identifiers": ["lytiva_1"],
        "name": "Lytiva Light 1",
        "manufacturer": "Lytiva",
        "model": "Smart Light",
    },
}

MOCK_SWITCH_DISCOVERY = {
    "name": "Test Switch",
    "unique_id": "lytiva_switch_1",
    "address": 2,
    "state_topic": "LYT/2/NODE/E/STATUS",
    "command_topic": "LYT/2/NODE/E/COMMAND",
    "device": {
        "identifiers": ["lytiva_2"],
        "name": "Lytiva Switch 1",
        "manufacturer": "Lytiva",
        "model": "Smart Switch",
    },
}

MOCK_SENSOR_DISCOVERY = {
    "name": "Test Sensor",
    "unique_id": "lytiva_sensor_1",
    "address": 3,
    "state_topic": "LYT/3/NODE/E/STATUS",
    "unit_of_measurement": "°C",
    "device_class": "temperature",
    "device": {
        "identifiers": ["lytiva_3"],
        "name": "Lytiva Sensor 1",
        "manufacturer": "Lytiva",
        "model": "Temperature Sensor",
    },
}

MOCK_COVER_DISCOVERY = {
    "name": "Test Cover",
    "unique_id": "lytiva_cover_1",
    "address": 4,
    "state_topic": "LYT/4/NODE/E/STATUS",
    "command_topic": "LYT/4/NODE/E/COMMAND",
    "device_class": "curtain",
    "device": {
        "identifiers": ["lytiva_4"],
        "name": "Lytiva Cover 1",
        "manufacturer": "Lytiva",
        "model": "Smart Curtain",
    },
}

MOCK_FAN_DISCOVERY = {
    "name": "Test Fan",
    "unique_id": "lytiva_fan_1",
    "address": 5,
    "state_topic": "LYT/5/NODE/E/STATUS",
    "command_topic": "LYT/5/NODE/E/COMMAND",
    "device": {
        "identifiers": ["lytiva_5"],
        "name": "Lytiva Fan 1",
        "manufacturer": "Lytiva",
        "model": "Smart Fan",
    },
}

MOCK_CLIMATE_DISCOVERY = {
    "name": "Test Climate",
    "unique_id": "lytiva_climate_1",
    "address": 6,
    "state_topic": "LYT/6/NODE/E/STATUS",
    "command_topic": "LYT/6/NODE/E/COMMAND",
    "temperature_state_topic": "LYT/6/NODE/E/STATUS",
    "temperature_command_topic": "LYT/6/NODE/E/COMMAND",
    "device": {
        "identifiers": ["lytiva_6"],
        "name": "Lytiva Climate 1",
        "manufacturer": "Lytiva",
        "model": "Smart Thermostat",
    },
}

# Mock status payloads
MOCK_LIGHT_STATUS_ON = {
    "address": 1,
    "unique_id": "lytiva_light_1",
    "state": "ON",
    "brightness": 255,
}

MOCK_LIGHT_STATUS_OFF = {
    "address": 1,
    "unique_id": "lytiva_light_1",
    "state": "OFF",
    "brightness": 0,
}

MOCK_SWITCH_STATUS_ON = {
    "address": 2,
    "unique_id": "lytiva_switch_1",
    "state": "ON",
}

MOCK_SWITCH_STATUS_OFF = {
    "address": 2,
    "unique_id": "lytiva_switch_1",
    "state": "OFF",
}
