"""Tests for Brother Printer integration."""
import json

from asynctest import patch

from homeassistant.components.brother.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TYPE

from tests.common import MockConfigEntry, load_fixture


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Brother integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HL-L2340DW 0123456789",
        unique_id="0123456789",
        data={CONF_HOST: "localhost", CONF_TYPE: "laser"},
    )
    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
