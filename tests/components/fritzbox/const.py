"""Constants for fritzbox tests."""
from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "10.0.0.1",
                CONF_PASSWORD: "fake_pass",
                CONF_USERNAME: "fake_user",
            }
        ]
    }
}

CONF_FAKE_NAME = "fake_name"
CONF_FAKE_AIN = "12345 1234567"
CONF_FAKE_MANUFACTURER = "fake_manufacturer"
CONF_FAKE_PRODUCTNAME = "fake_productname"
