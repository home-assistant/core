"""Common stuff for Vodafone Station tests."""
from homeassistant.components.vodafone_station.const import DOMAIN
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
)

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_USERNAME: "fake_username",
                CONF_PASSWORD: "fake_password",
                CONF_SSL: True,
            }
        ]
    }
}

MOCK_USER_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
