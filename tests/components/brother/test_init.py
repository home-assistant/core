"""Test init of Brother integration."""
import json

from asynctest import patch
import pytest

import homeassistant.components.brother as brother
from homeassistant.components.brother.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TYPE, STATE_UNAVAILABLE
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry, load_fixture


async def test_async_setup_entry(hass):
    """Test a successful setup entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HL-L2340DW 0123456789",
        data={CONF_HOST: "localhost", CONF_TYPE: "laser"},
    )
    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.hl_l2340dw_status")
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "waiting"


async def test_config_not_ready(hass):
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HL-L2340DW 0123456789",
        data={CONF_HOST: "localhost", CONF_TYPE: "laser"},
    )
    with patch(
        "brother.Brother._get_data", side_effect=ConnectionError()
    ), pytest.raises(ConfigEntryNotReady):
        await brother.async_setup_entry(hass, entry)


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HL-L2340DW 0123456789",
        data={CONF_HOST: "localhost", CONF_TYPE: "laser"},
    )
    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.data[DOMAIN][entry.entry_id]

        assert await hass.config_entries.async_unload(entry.entry_id)
        assert not hass.data[DOMAIN]
