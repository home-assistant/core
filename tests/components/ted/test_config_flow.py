"""Tests for the TED config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.ted import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME

CONFIG = {CONF_HOST: "127.0.0.1"}
CONFIG_FINAL = {CONF_HOST: "127.0.0.1", CONF_NAME: "TED ted5000"}


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch("tedpy.TED5000.check", return_value=True), patch(
        "tedpy.TED5000.update", return_value=True
    ), patch(
        "homeassistant.components.ted.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == CONFIG_FINAL
    assert len(mock_setup_entry.mock_calls) == 1
