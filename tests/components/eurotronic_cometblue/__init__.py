"""Tests for the Eurotronic Comet Blue integration."""

from eurotronic_cometblue_ha import const as cometblue_const

from homeassistant.const import CONF_PIN

FIXTURE_DEVICE_NAME = "Comet Blue"
FIXTURE_MAC = "aa:bb:cc:dd:ee:ff"
FIXTURE_RSSI = -60
FIXTURE_SERVICE_UUID = "47e9ee00-47e9-11e4-8939-164230d1df67"

WRITEABLE_CHARACTERISTICS = [
    cometblue_const.CHARACTERISTIC_DATETIME,
    cometblue_const.CHARACTERISTIC_MONDAY,
    cometblue_const.CHARACTERISTIC_TUESDAY,
    cometblue_const.CHARACTERISTIC_WEDNESDAY,
    cometblue_const.CHARACTERISTIC_THURSDAY,
    cometblue_const.CHARACTERISTIC_FRIDAY,
    cometblue_const.CHARACTERISTIC_SATURDAY,
    cometblue_const.CHARACTERISTIC_SUNDAY,
    cometblue_const.CHARACTERISTIC_HOLIDAY_1,
    cometblue_const.CHARACTERISTIC_SETTINGS,
    cometblue_const.CHARACTERISTIC_TEMPERATURE,
    cometblue_const.CHARACTERISTIC_PIN,
]
WRITEABLE_CHARACTERISTICS_ALLOW_UNCHANGED = [
    cometblue_const.CHARACTERISTIC_SETTINGS,
    cometblue_const.CHARACTERISTIC_TEMPERATURE,
]

FIXTURE_DEFAULT_CHARACTERISTICS = {
    cometblue_const.CHARACTERISTIC_MODEL: b"Comet Blue",
    cometblue_const.CHARACTERISTIC_VERSION: b"0.0.10",
    cometblue_const.CHARACTERISTIC_MANUFACTURER: b"Eurotronic GmbH",
    cometblue_const.CHARACTERISTIC_HOLIDAY_1: [
        128,
        27,
        11,
        22,
        128,
        27,
        11,
        22,
        34,
    ],
    cometblue_const.CHARACTERISTIC_TEMPERATURE: [
        41,
        40,
        34,
        42,
        0,
        4,
        10,
    ],
    cometblue_const.CHARACTERISTIC_BATTERY: b"48",
    cometblue_const.CHARACTERISTIC_MONDAY: [37, 137, 0, 0, 0, 0, 0, 0],
    cometblue_const.CHARACTERISTIC_TUESDAY: [37, 137, 0, 0, 0, 0, 0, 0],
    cometblue_const.CHARACTERISTIC_WEDNESDAY: [37, 137, 0, 0, 0, 0, 0, 0],
    cometblue_const.CHARACTERISTIC_THURSDAY: [37, 137, 0, 0, 0, 0, 0, 0],
    cometblue_const.CHARACTERISTIC_FRIDAY: [0, 1, 10, 20, 21, 130, 140, 143],
    cometblue_const.CHARACTERISTIC_SATURDAY: [37, 137, 0, 0, 0, 0, 0, 0],
    cometblue_const.CHARACTERISTIC_SUNDAY: [37, 137, 0, 0, 0, 0, 0, 0],
}

FIXTURE_USER_INPUT = {
    CONF_PIN: "000000",
}
