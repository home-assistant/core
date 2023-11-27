"""Constants used for Insteon test cases."""
from homeassistant.components.insteon.const import (
    CONF_CAT,
    CONF_DIM_STEPS,
    CONF_HOUSECODE,
    CONF_SUBCAT,
    CONF_UNITCODE,
    X10_PLATFORMS,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_USERNAME,
)

MOCK_HOSTNAME = "1.1.1.1"
MOCK_DEVICE = "/dev/ttyUSB55"
MOCK_USERNAME = "test-username"
MOCK_PASSWORD = "test-password"
MOCK_PORT = 4567

MOCK_ADDRESS = "1a2b3c"
MOCK_CAT = 0x02
MOCK_SUBCAT = 0x1A

MOCK_HOUSECODE = "c"
MOCK_UNITCODE_1 = 1
MOCK_UNITCODE_2 = 2
MOCK_X10_PLATFORM_1 = X10_PLATFORMS[0]
MOCK_X10_PLATFORM_2 = X10_PLATFORMS[2]
MOCK_X10_STEPS = 10

MOCK_USER_INPUT_PLM = {
    CONF_DEVICE: MOCK_DEVICE,
}

MOCK_USER_INPUT_PLM_MANUAL = {
    CONF_DEVICE: "manual",
}

MOCK_USER_INPUT_HUB_V2 = {
    CONF_HOST: MOCK_HOSTNAME,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_PORT: MOCK_PORT,
}

MOCK_USER_INPUT_HUB_V1 = {
    CONF_HOST: MOCK_HOSTNAME,
    CONF_PORT: MOCK_PORT,
}

MOCK_DEVICE_OVERRIDE_CONFIG = {
    CONF_ADDRESS: MOCK_ADDRESS,
    CONF_CAT: MOCK_CAT,
    CONF_SUBCAT: MOCK_SUBCAT,
}

MOCK_X10_CONFIG_1 = {
    CONF_HOUSECODE: MOCK_HOUSECODE,
    CONF_UNITCODE: MOCK_UNITCODE_1,
    CONF_PLATFORM: MOCK_X10_PLATFORM_1,
    CONF_DIM_STEPS: MOCK_X10_STEPS,
}

MOCK_X10_CONFIG_2 = {
    CONF_HOUSECODE: MOCK_HOUSECODE,
    CONF_UNITCODE: MOCK_UNITCODE_2,
    CONF_PLATFORM: MOCK_X10_PLATFORM_2,
    CONF_DIM_STEPS: MOCK_X10_STEPS,
}

PATCH_CONNECTION = "homeassistant.components.insteon.config_flow.async_connect"
PATCH_CONNECTION_CLOSE = "homeassistant.components.insteon.config_flow.async_close"
PATCH_DEVICES = "homeassistant.components.insteon.config_flow.devices"
PATCH_USB_LIST = "homeassistant.components.insteon.config_flow.async_get_usb_ports"
PATCH_ASYNC_SETUP = "homeassistant.components.insteon.async_setup"
PATCH_ASYNC_SETUP_ENTRY = "homeassistant.components.insteon.async_setup_entry"
