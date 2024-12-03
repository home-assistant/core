"""Tests for the WeConnect integration."""

from typing import Any

from homeassistant.components.weconnect.const import CONF_SPIN, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

MOCK_CONFIG_DATA: dict[str, Any] = {
    CONF_PASSWORD: "password",
    CONF_USERNAME: "username",
    CONF_SPIN: "",
}

MOCK_CONFIG_ENTRY: dict[str, Any] = {
    "domain": DOMAIN,
    "entry_id": "1",
    "source": "user",
    "title": MOCK_CONFIG_DATA[CONF_USERNAME],
    "data": MOCK_CONFIG_DATA,
}
