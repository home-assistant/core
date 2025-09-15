"""Tests for the Smart Meter B-route integration."""

from homeassistant.components.smart_meter_b_route.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

user_input = {
    CONF_DEVICE: "/dev/ttyUSB42",
    CONF_ID: "B_ROUTE_ID",
    CONF_PASSWORD: "B_ROUTE_PASSWORD",
}


def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=user_input,
        entry_id="01234567890123456789012345F789",
        unique_id="123456",
    )
    entry.add_to_hass(hass)

    return entry
