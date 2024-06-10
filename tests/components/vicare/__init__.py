"""Test for ViCare."""

from __future__ import annotations

from typing import Final

from homeassistant.components.vicare.const import CONF_HEATING_TYPE
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME

MODULE = "homeassistant.components.vicare"

ENTRY_CONFIG: Final[dict[str, str]] = {
    CONF_USERNAME: "foo@bar.com",
    CONF_PASSWORD: "1234",
    CONF_CLIENT_ID: "5678",
    CONF_HEATING_TYPE: "auto",
}

MOCK_MAC = "B874241B7B9"
