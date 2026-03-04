"""Tests for the Config Flow for Google Wifi."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.google_wifi.config_flow import (
    CannotConnect,
    InvalidIPAddress,
)
from homeassistant.components.google_wifi.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test successful form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    with (
        patch(
            "homeassistant.components.google_wifi.config_flow.requests.get"
        ) as mock_get,
        patch(
            "homeassistant.components.google_wifi.async_setup_entry", return_value=True
        ),
    ):
        mock_get.return_value.status_code = 200

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "192.168.86.1", CONF_NAME: "Main Router"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_IP_ADDRESS] == "192.168.86.1"


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (InvalidIPAddress, "invalid_ip"),
        (CannotConnect, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(hass: HomeAssistant, side_effect, error_key) -> None:
    """Test we handle validation errors."""
    # Add the missing context here
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.google_wifi.config_flow.validate_input",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "1.1.1.1", CONF_NAME: "Main Router"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"]["base"] == error_key


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test the reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_IP_ADDRESS: "1.1.1.1", CONF_NAME: "Old"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.google_wifi.config_flow.requests.get"
    ) as mock_get:
        mock_get.return_value.status_code = 200
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "1.1.1.2", CONF_NAME: "New"}
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data[CONF_IP_ADDRESS] == "1.1.1.2"
