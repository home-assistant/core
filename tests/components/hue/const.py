"""Constants for Hue tests."""


FAKE_DEVICE = {
    "id": "fake_device_id_1",
    "id_v1": "/lights/1",
    "metadata": {"archetype": "unknown_archetype", "name": "Hue mocked device"},
    "product_data": {
        "certified": True,
        "manufacturer_name": "Signify Netherlands B.V.",
        "model_id": "abcdefg",
        "product_archetype": "unknown_archetype",
        "product_name": "Hue Mocked on/off light with a sensor",
        "software_version": "1.88.1",
    },
    "services": [
        {"rid": "fake_light_id_1", "rtype": "light"},
        {"rid": "fake_zigbee_connectivity_id_1", "rtype": "zigbee_connectivity"},
        {"rid": "fake_temperature_sensor_id_1", "rtype": "temperature"},
    ],
    "type": "device",
}

FAKE_LIGHT = {
    "alert": {"action_values": ["breathe"]},
    "dynamics": {
        "speed": 0.0,
        "speed_valid": False,
        "status": "none",
        "status_values": ["none"],
    },
    "id": "fake_light_id_1",
    "id_v1": "/lights/1",
    "metadata": {"archetype": "unknown", "name": "Hue fake light 1"},
    "mode": "normal",
    "on": {"on": False},
    "owner": {"rid": "fake_device_id_1", "rtype": "device"},
    "type": "light",
}

FAKE_ZIGBEE_CONNECTIVITY = {
    "id": "fake_zigbee_connectivity_id_1",
    "id_v1": "/lights/29",
    "mac_address": "00:01:02:03:04:05:06:07",
    "owner": {"rid": "fake_device_id_1", "rtype": "device"},
    "status": "connected",
    "type": "zigbee_connectivity",
}

FAKE_SENSOR = {
    "enabled": True,
    "id": "fake_temperature_sensor_id_1",
    "id_v1": "/sensors/1",
    "owner": {"rid": "fake_device_id_1", "rtype": "device"},
    "temperature": {"temperature": 18.0, "temperature_valid": True},
    "type": "temperature",
}
