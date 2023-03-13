"""Constants for SFR Box tests."""
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.sensor import ATTR_OPTIONS, ATTR_STATE_CLASS
from homeassistant.components.sfr_box.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_IDENTIFIERS,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_SW_VERSION,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    Platform,
)

ATTR_DEFAULT_DISABLED = "default_disabled"
ATTR_UNIQUE_ID = "unique_id"
FIXED_ATTRIBUTES = (
    ATTR_DEVICE_CLASS,
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
)

EXPECTED_ENTITIES = {
    "expected_device": {
        ATTR_IDENTIFIERS: {(DOMAIN, "e4:5d:51:00:11:22")},
        ATTR_MODEL: "NB6VAC-FXC-r0",
        ATTR_NAME: "SFR Box",
        ATTR_SW_VERSION: "NB6VAC-MAIN-R4.0.44k",
    },
    Platform.BUTTON: [
        {
            ATTR_DEVICE_CLASS: ButtonDeviceClass.RESTART,
            ATTR_ENTITY_ID: "button.sfr_box_reboot",
            ATTR_STATE: STATE_UNKNOWN,
            ATTR_UNIQUE_ID: "e4:5d:51:00:11:22_system_reboot",
        },
    ],
}
