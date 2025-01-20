"""Constants for Foscam tests."""

from homeassistant.components.foscam import config_flow

VALID_CONFIG = {
    config_flow.CONF_HOST: "10.0.0.2",
    config_flow.CONF_PORT: 88,
    config_flow.CONF_USERNAME: "admin",
    config_flow.CONF_PASSWORD: "1234",
    config_flow.CONF_STREAM: "Main",
    config_flow.CONF_RTSP_PORT: 554,
}
OPERATOR_CONFIG = {
    config_flow.CONF_USERNAME: "operator",
}
INVALID_RESPONSE_CONFIG = {
    config_flow.CONF_USERNAME: "interr",
}
CAMERA_NAME = "Mocked Foscam Camera"
CAMERA_MAC = "C0:C1:D0:F4:B4:D4"
ENTRY_ID = "123ABC"
