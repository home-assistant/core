"""Test the Vemmio config flow."""

from unittest.mock import patch

from vemmio_client import DeviceInfo

from homeassistant import config_entries
from homeassistant.components.vemmio.const import CONF_REVISION, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.vemmio.config_flow.get_info",
            return_value=DeviceInfo("AA:BB:CC:DD:EE:FF", "Implant", "0.1.2"),
        ),
        patch(
            "homeassistant.components.vemmio.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 8080},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Implant aa:bb:cc:dd:ee:ff"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 8080,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_TYPE: "Implant",
        CONF_REVISION: "0.1.2",
    }
    assert len(mock_setup_entry.mock_calls) == 1
