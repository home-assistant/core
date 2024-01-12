"""Define tests for Wittiot integration."""
from __future__ import annotations

from unittest.mock import patch

from wittiot.errors import WittiotError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.wittiot.const import (
    CONF_IP,
    CONNECTION_TYPE,
    DEVICE_NAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FAKE_CONFIG = {
    DEVICE_NAME: "GW2000-WIFIXXXX",
    CONF_IP: "1.1.1.1",
    CONNECTION_TYPE: "Local",
}

DEV_INFO = {
    "dev_name": "GW2000-WIFIXXXX",
    "mac": "AA:AA:AA:AA:AA:AA",
    "ver": "GW2000_V1.0.0",
}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test connection to host error."""

    with patch(
        "homeassistant.components.wittiot.config_flow.API.request_loc_info",
        side_effect=WittiotError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FAKE_CONFIG
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the config entry is created."""
    with patch(
        "homeassistant.components.wittiot.config_flow.API.request_loc_info",
        return_value=DEV_INFO,
    ), patch(
        "homeassistant.components.wittiot.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FAKE_CONFIG
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == FAKE_CONFIG


async def test_duplicate_error(
    hass: HomeAssistant,
) -> None:
    """Test that errors are shown when duplicates are added."""
    MockConfigEntry(
        domain=DOMAIN, unique_id=DEV_INFO["dev_name"], data=FAKE_CONFIG
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.wittiot.config_flow.API.request_loc_info",
        return_value=DEV_INFO,
    ), patch(
        "homeassistant.components.wittiot.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FAKE_CONFIG
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
