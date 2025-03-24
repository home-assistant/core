"""Tests for the devolo Home Network integration."""

from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DISCOVERY_INFO, IP

from tests.common import MockConfigEntry


def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    config = {
        CONF_IP_ADDRESS: IP,
        CONF_PASSWORD: "test",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        entry_id="123456",
        unique_id=DISCOVERY_INFO.properties["SN"],
    )
    entry.add_to_hass(hass)

    return entry
