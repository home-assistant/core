"""Tests for the Philips TV integration."""

MOCK_SERIAL_NO = "1234567890"
MOCK_NAME = "Philips TV"

MOCK_SYSTEM = {
    "menulanguage": "English",
    "name": MOCK_NAME,
    "country": "Sweden",
    "serialnumber": MOCK_SERIAL_NO,
    "softwareversion": "abcd",
    "model": "modelname",
}

MOCK_USERINPUT = {
    "host": "1.1.1.1",
    "api_version": 1,
}

MOCK_CONFIG = {
    **MOCK_USERINPUT,
    "system": MOCK_SYSTEM,
}

MOCK_ENTITY_ID = "media_player.philips_tv"
