"""Constants for Airthings integration tests."""

from homeassistant.components.airthings import AirthingsDevice
from homeassistant.components.airthings.const import CONF_SECRET
from homeassistant.const import CONF_ID

TEST_DATA = {
    CONF_ID: "client_id",
    CONF_SECRET: "secret",
}

WAVE_RADON: dict[str, AirthingsDevice] = {
    "2950000001": AirthingsDevice(
        device_id="2950000001",
        name="Basement",
        sensors={
            "battery": 100,
            "humidity": 75.0,
            "radonShortTermAvg": 537.0,
            "rssi": -76,
            "temp": 16.6,
        },
        is_active=None,
        location_name="Home",
        device_type="WAVE_GEN2",
        product_name="Wave",
    )
}

WAVE_ENHANCE: dict[str, AirthingsDevice] = {
    "3210000001": AirthingsDevice(
        device_id="3210000001",
        name="Bedroom",
        sensors={
            "battery": 35,
            "co2": 551.0,
            "humidity": 43.0,
            "lux": 1.0,
            "pressure": 985.0,
            "rssi": -67,
            "sla": 34.0,
            "temp": 21.9,
            "voc": 158.0,
        },
        is_active=None,
        location_name="Home",
        device_type="WAVE_ENHANCE",
        product_name="Wave Enhance",
    ),
}

VIEW_PLUS: dict[str, AirthingsDevice] = {
    "2960000001": AirthingsDevice(
        device_id="2960000001",
        name="Office",
        sensors={
            "battery": 77,
            "co2": 876.0,
            "humidity": 42.0,
            "pm1": 3.0,
            "pm25": 3.0,
            "pressure": 985.0,
            "radonShortTermAvg": 15.0,
            "rssi": 0,
            "temp": 24.5,
            "voc": 1842.0,
        },
        is_active=None,
        location_name="Office",
        device_type="VIEW_PLUS",
        product_name="View Plus",
    ),
}

THREE_DEVICES: dict[str, AirthingsDevice] = {
    **WAVE_RADON,
    **WAVE_ENHANCE,
    **VIEW_PLUS,
}

TWO_DEVICES: dict[str, AirthingsDevice] = {
    **WAVE_RADON,
    **VIEW_PLUS,
}
