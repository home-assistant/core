"""Tests for the Config Flow for Google Wifi."""

from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.google_wifi.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.google_wifi.config_flow.validate_input",
            return_value={"title": "192.168.86.1"},
        ),
        patch(
            "homeassistant.components.google_wifi.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
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
    assert result2["data"] == {
        CONF_IP_ADDRESS: "192.168.86.1",
        CONF_NAME: "Main Router",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_ip(hass: HomeAssistant) -> None:
    """Test we handle invalid IP error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "not-an-ip",
            CONF_NAME: "Router",
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_ip"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test handling of unexpected exceptions (Line 52-54)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.google_wifi.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "1.1.1.1", CONF_NAME: "Router"}
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test the reconfiguration flow (Lines 82-94)."""
    # Setup an existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1", CONF_NAME: "Old Name"},
        unique_id="1.1.1.1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    with patch("homeassistant.components.google_wifi.config_flow.validate_input"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "1.1.1.2", CONF_NAME: "New Name"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data[CONF_IP_ADDRESS] == "1.1.1.2"
