"""Common utils for Litter-Robot tests."""

from homeassistant.components.litterrobot import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

CONFIG = {DOMAIN: {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"}}

ACCOUNT_USER_ID = "1234567"

VACUUM_ENTITY_ID = "vacuum.test_litter_box"
