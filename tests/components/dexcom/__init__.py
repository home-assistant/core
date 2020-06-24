"""Tests for the Dexcom integration."""

import json

from pydexcom import GlucoseReading

from homeassistant.components.dexcom.const import CONF_SERVER, DOMAIN, SERVER_US
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch
from tests.common import MockConfigEntry, load_fixture

CONFIG = {
    CONF_USERNAME: "test_username",
    CONF_PASSWORD: "test_password",
    CONF_SERVER: SERVER_US,
}

GLUCOSE_READING = GlucoseReading(json.loads(load_fixture("dexcom_data.json")))


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Dexcom integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_username",
        unique_id="test_username",
        data=CONFIG,
        options=None,
    )
    with patch(
        "homeassistant.components.dexcom.Dexcom.get_current_glucose_reading",
        return_value=GLUCOSE_READING,
    ), patch(
        "homeassistant.components.dexcom.Dexcom.create_session",
        return_value="test_session_id",
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
