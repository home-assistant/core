"""Tests for the local_ip config_flow."""
from homeassistant import data_entry_flow
from homeassistant.components.local_ip.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER

from tests.common import MockConfigEntry


async def test_config_flow(hass):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()
    state = hass.states.get(f"sensor.{DOMAIN}")
    assert state


async def test_already_setup(hass):
    """Test we abort if already setup."""
    MockConfigEntry(domain=DOMAIN, data={},).add_to_hass(hass)

    # Should fail, same NAME
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"
