"""Test the Netis Router config flow and options flow."""

from __future__ import annotations

import pytest

from homeassistant.components.netis.api import (
    NetisAuthError,
    NetisConnectionError,
    NetisError,
)
from homeassistant.components.netis.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_step_show_form(hass: HomeAssistant) -> None:
    """The user step should render an empty form on first invocation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_HOST in result["data_schema"].schema


async def test_user_step_success(
    hass: HomeAssistant, mock_netis_client
) -> None:
    """A valid connection test should create the config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "password"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Netis 192.168.1.1"
    assert result["data"] == {CONF_HOST: "192.168.1.1", CONF_PASSWORD: "password"}
    assert result["result"].unique_id == "192.168.1.1"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (NetisAuthError("bad creds"), "invalid_auth"),
        (NetisConnectionError("down"), "cannot_connect"),
        (NetisError("unexpected"), "unknown"),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_netis_client,
    side_effect: Exception,
    reason: str,
) -> None:
    """Each API error type should map to its user-facing error key."""
    mock_netis_client.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "password"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": reason}


async def test_user_step_already_configured(
    hass: HomeAssistant, mock_config_entry, mock_netis_client
) -> None:
    """Submitting a host that already has an entry should abort."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: "password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, init_integration
) -> None:
    """The options flow should let the user change the polling interval."""
    entry = init_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"scan_interval": 60},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["scan_interval"] == 60
