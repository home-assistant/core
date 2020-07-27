"""Test init of Brother integration."""
from homeassistant.components.brother.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import CONF_HOST, CONF_TYPE, STATE_UNAVAILABLE

from tests.async_mock import patch
from tests.common import MockConfigEntry
from tests.components.brother import init_integration


async def test_async_setup_entry(hass):
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("sensor.hl_l2340dw_status")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "waiting"


async def test_config_not_ready(hass):
    """Test for setup failure if connection to broker is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HL-L2340DW 0123456789",
        unique_id="0123456789",
        data={CONF_HOST: "localhost", CONF_TYPE: "laser"},
    )

    with patch("brother.Brother._get_data", side_effect=ConnectionError()):
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
