"""Common stuff for Comelit SimpleHome tests."""
from homeassistant.components.comelit.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PIN

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_PIN: "1234",
            }
        ]
    }
}

MOCK_USER_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
