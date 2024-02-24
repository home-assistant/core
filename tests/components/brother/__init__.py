"""Tests for Brother Printer integration."""
import json
from unittest.mock import patch

from homeassistant.components.brother.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


async def init_integration(
    hass: HomeAssistant, skip_setup: bool = False
) -> MockConfigEntry:
    """Set up the Brother integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HL-L2340DW 0123456789",
        unique_id="0123456789",
        data={CONF_HOST: "localhost", CONF_TYPE: "laser"},
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        with patch("brother.Brother.initialize"), patch(
            "brother.Brother._get_data",
            return_value=json.loads(load_fixture("printer_data.json", "brother")),
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    return entry
