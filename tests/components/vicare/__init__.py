"""Test for ViCare."""
from __future__ import annotations

from typing import Final

from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME

# When running tests with HA Core ViCare:
MODULE = "homeassistant.components.vicare"

# When running tests with Custom ViCare Integration:
# MODULE = "custom_components.vicare"
# sys.modules["tests.common"] = pytest_homeassistant_custom_component.common


ENTRY_CONFIG: Final[dict[str, str]] = {
    CONF_USERNAME: "foo@bar.com",
    CONF_PASSWORD: "1234",
    CONF_CLIENT_ID: "5678",
}

MOCK_MAC = "B874241B7B9"
