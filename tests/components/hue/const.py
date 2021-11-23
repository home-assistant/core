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
        {"rid": "fake_motion_sensor_id_1", "rtype": "motion"},
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

FAKE_BINARY_SENSOR = {
    "enabled": True,
    "id": "fake_motion_sensor_id_1",
    "id_v1": "/sensors/2",
    "motion": {"motion": False, "motion_valid": True},
    "owner": {"rid": "fake_device_id_1", "rtype": "device"},
    "type": "motion",
}

FAKE_SCENE = {
    "actions": [
        {
            "action": {
                "color_temperature": {"mirek": 156},
                "dimming": {"brightness": 65.0},
                "on": {"on": True},
            },
            "target": {"rid": "3a6710fa-4474-4eba-b533-5e6e72968feb", "rtype": "light"},
        },
        {
            "action": {"on": {"on": True}},
            "target": {"rid": "7697ac8a-25aa-4576-bb40-0036c0db15b9", "rtype": "light"},
        },
    ],
    "group": {"rid": "6ddc9066-7e7d-4a03-a773-c73937968296", "rtype": "room"},
    "id": "fake_scene_id_1",
    "id_v1": "/scenes/test",
    "metadata": {
        "image": {
            "rid": "7fd2ccc5-5749-4142-b7a5-66405a676f03",
            "rtype": "public_image",
        },
        "name": "Mocked Scene",
    },
    "palette": {"color": [], "color_temperature": [], "dimming": []},
    "speed": 0.5,
    "type": "scene",
}
