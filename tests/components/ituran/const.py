"""Constants for tests of the Ituran component."""

from typing import Any

from homeassistant.components.ituran.const import (
    CONF_ID_OR_PASSPORT,
    CONF_MOBILE_ID,
    CONF_PHONE_NUMBER,
    DOMAIN,
)

MOCK_CONFIG_DATA: dict[str, str] = {
    CONF_ID_OR_PASSPORT: "12345678",
    CONF_PHONE_NUMBER: "0501234567",
    CONF_MOBILE_ID: "0123456789abcdef",
}

MOCK_CONFIG_ENTRY: dict[str, Any] = {
    "domain": DOMAIN,
    "entry_id": "1",
    "source": "user",
    "title": MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT],
    "data": MOCK_CONFIG_DATA,
}
