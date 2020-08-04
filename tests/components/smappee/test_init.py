"""Tests for the Smappee component init module."""
from homeassistant import data_entry_flow
from homeassistant.components.smappee.const import (
    CONF_HOSTNAME,
    CONF_SERIALNUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_ZEROCONF

from tests.async_mock import patch


async def test_unload_config_entry(hass):
    """Test unload config entry flow."""
    with patch("pysmappee.api.SmappeeLocalApi.logon", return_value={}), patch(
        "pysmappee.api.SmappeeLocalApi.load_advanced_config",
        return_value=[{"key": "mdnsHostName", "value": "Smappee1006000212"}],
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_command_control_config", return_value=[]
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_instantaneous",
        return_value=[{"key": "phase0ActivePower", "value": 0}],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data={
                "host": "1.2.3.4",
                "port": 22,
                CONF_HOSTNAME: "Smappee1006000212.local.",
                "type": "_ssh._tcp.local.",
                "name": "Smappee1006000212._ssh._tcp.local.",
                "properties": {"_raw": {}},
            },
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "zeroconf_confirm"
        assert result["description_placeholders"] == {CONF_SERIALNUMBER: "1006000212"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Smappee1006000212"
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert not hass.data.get(DOMAIN)
