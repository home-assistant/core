"""Tests for Steam integration."""

from homeassistant.components.steam_online.const import CONF_ACCOUNT
from homeassistant.const import CONF_API_KEY

API_KEY = "abc123"
ACCOUNT_1 = "12345678901234567"
ACCOUNT_2 = "12345678912345678"
ACCOUNT_NAME_1 = "testaccount1"
ACCOUNT_NAME_2 = "testaccount2"

CONF_DATA = {
    CONF_API_KEY: API_KEY,
    CONF_ACCOUNT: ACCOUNT_1,
}
