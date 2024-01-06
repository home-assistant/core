"""Common stuff for Comelit SimpleHome tests."""

from aiocomelit.const import VEDO

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_PORT: 80,
                CONF_PIN: 1234,
            },
            {
                CONF_HOST: "fake_vedo_host",
                CONF_PORT: 8080,
                CONF_PIN: 1234,
                CONF_TYPE: VEDO,
            },
        ]
    }
}

MOCK_USER_BRIDGE_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
MOCK_USER_VEDO_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][1]

FAKE_PIN = 5678
