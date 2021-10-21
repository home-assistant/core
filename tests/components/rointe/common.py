"""Common data for Rointe tests."""

import json

from rointesdk.rointe_api import ApiResponse

from homeassistant.components.rointe import (
    CONF_INSTALLATION,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

USERNAME = "rointe@home-assistant.com"
PASSWORD = "test-password"
LOCAL_ID = "local-1234"
INSTALLATION_HOME_ID = "install-home"

MOCK_CONFIG = {
    CONF_INSTALLATION: INSTALLATION_HOME_ID,
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
}

MOCK_GET_DEVICES_RESPONSE = ApiResponse(True, ["device-1", "device-2"], None)

MOCK_GET_DEVICE_RESPONSES = {
    "device-1": ApiResponse(
        True,
        json.loads(load_fixture("device_1_data.json", "rointe")),
        None,
    ),
    "device-2": ApiResponse(
        True,
        json.loads(load_fixture("device_2_data.json", "rointe")),
        None,
    ),
}

DOMAIN = "rointe"


async def async_init_integration(
    hass: HomeAssistant,
) -> None:
    """Set up the Airzone integration in Home Assistant."""
    config_entry = MockConfigEntry(
        data=MOCK_CONFIG,
        domain=DOMAIN,
        unique_id="rointe_unique_id",
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
