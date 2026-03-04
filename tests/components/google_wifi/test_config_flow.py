"""Tests for the Config Flow for Google Wifi."""

from unittest.mock import patch, MagicMock
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.google_wifi.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry

async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    with (
        patch(
            "homeassistant.components.google_wifi.config_flow.requests.get"
        ) as mock_get,
        patch(
            "homeassistant.components.google_wifi.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        mock_get.return_value.status_code = 200

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.86.1",
                CONF_NAME: "Main Router",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Main Router"
    assert result2["data"][CONF_IP_ADDRESS] == "192.168.86.1"

async def test_import_flow(hass: HomeAssistant) -> None:
    """Test the import flow from YAML."""
    with patch("homeassistant.components.google_wifi.config_flow.requests.get") as mock_get:
        mock_get.return_value.status_code = 200

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_IP_ADDRESS: "192.168.86.1", CONF_NAME: "Imported Wifi"},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_IP_ADDRESS] == "192.168.86.1"
