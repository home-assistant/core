"""Tests for the Fully Kiosk Browser integration."""
import json

from asynctest import patch

from homeassistant.components.fully_kiosk.const import DOMAIN

from tests.common import MockConfigEntry, load_fixture


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Fully Kiosk Browser integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.234",
            "password": "test-password",
        },
    )

    deviceinfo = json.loads(load_fixture("fully_kiosk/deviceinfo.json"))

    with patch(
        "homeassistant.components.fully_kiosk.coordinator.FullyKioskDataUpdateCoordinator._async_update_data",
        return_value=deviceinfo,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
