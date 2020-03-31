"""Tests for the local_ip config_flow."""
from homeassistant import data_entry_flow
from homeassistant.components.local_ip import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry


async def test_config_flow(hass):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "test"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == "test"

    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    assert state


async def test_already_setup(hass):
    """Test we abort if the name is already setup."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "test"}, unique_id="test",
    ).add_to_hass(hass)

    # Should fail, same NAME
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_NAME: "test"},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
