"""Common stuff for Comelit SimpleHome tests."""
from aiocomelit.const import BRIDGE

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICES,
    CONF_HOST,
    CONF_PIN,
    CONF_PORT,
)

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_PORT: 80,
                CONF_PIN: 1234,
                CONF_DEVICE: BRIDGE,
            }
        ]
    }
}

MOCK_USER_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
