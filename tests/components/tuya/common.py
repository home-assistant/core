"""Test code shared between test files."""

from tuyaha.devices import climate, light, switch

CLIMATE_ID = "1"
CLIMATE_DATA = {
    "data": {"state": "true", "temp_unit": climate.UNIT_CELSIUS},
    "id": CLIMATE_ID,
    "ha_type": "climate",
    "name": "TestClimate",
    "dev_type": "climate",
}

LIGHT_ID = "2"
LIGHT_DATA = {
    "data": {"state": "true"},
    "id": LIGHT_ID,
    "ha_type": "light",
    "name": "TestLight",
    "dev_type": "light",
}

LIGHT_ID_FAKE = "9999"
LIGHT_DATA_FAKE = {
    "data": {"state": "true"},
    "id": LIGHT_ID_FAKE,
    "ha_type": "light",
    "name": "TestLightFake",
    "dev_type": "light",
}

SWITCH_ID = "3"
SWITCH_DATA = {
    "data": {"state": True},
    "id": SWITCH_ID,
    "ha_type": "switch",
    "name": "TestSwitch",
    "dev_type": "switch",
}

TUYA_DEVICES = [
    climate.TuyaClimate(CLIMATE_DATA, None),
    light.TuyaLight(LIGHT_DATA, None),
    light.TuyaLight(LIGHT_DATA_FAKE, None),
    switch.TuyaSwitch(SWITCH_DATA, None),
]


class MockTuya:
    """Mock for Tuya devices."""

    def get_all_devices(self):
        """Return all configured devices."""
        return TUYA_DEVICES

    def get_device_by_id(self, dev_id):
        """Return configured device with dev id."""
        for device in TUYA_DEVICES:
            if device.object_id() == dev_id:
                if dev_id == LIGHT_ID_FAKE:
                    return None
                return device
        return None
