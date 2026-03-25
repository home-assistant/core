"""Reusable fixtures for justnimbus tests."""

from homeassistant.components.justnimbus.const import CONF_ZIP_CODE
from homeassistant.const import CONF_CLIENT_ID

FIXTURE_OLD_USER_INPUT = {CONF_CLIENT_ID: "test_id"}
FIXTURE_USER_INPUT = {CONF_CLIENT_ID: "test_id", CONF_ZIP_CODE: "test_zip"}
FIXTURE_UNIQUE_ID = "test_idtest_zip"
