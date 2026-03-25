"""Constants for the laundrify tests."""

from homeassistant.const import CONF_CODE

VALID_AUTH_CODE = "999-001"
VALID_ACCESS_TOKEN = "validAccessToken1234"
VALID_ACCOUNT_ID = "1234"

VALID_USER_INPUT = {
    CONF_CODE: VALID_AUTH_CODE,
}
