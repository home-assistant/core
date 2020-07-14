"""Test init of the growatt_rs232 inverter integration."""
from growattRS232 import ATTR_SERIAL_NUMBER, ATTR_STATUS_CODE

from homeassistant.components.growatt_rs232.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import STATE_UNAVAILABLE

from .const import CONFIG, PATCH, TITLE, UNIQUE_ID, VALUES

from tests.async_mock import patch
from tests.common import MockConfigEntry
from tests.components.growatt_rs232 import init_integration


async def test_async_setup_entry(hass):
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get(f"sensor.{VALUES[ATTR_SERIAL_NUMBER]}_{ATTR_STATUS_CODE}")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == str(VALUES[ATTR_STATUS_CODE])


async def test_config_not_ready(hass):
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN, title=TITLE, unique_id=UNIQUE_ID, data=CONFIG,
    )

    with patch(PATCH, side_effect=ConnectionError()):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
