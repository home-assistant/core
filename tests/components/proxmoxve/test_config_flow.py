"""Test the config flow for Proxmox VE."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from proxmoxer import AuthenticationError
import pytest
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.proxmoxve import CONF_HOST, CONF_REALM
from homeassistant.components.proxmoxve.common import ResourceException
from homeassistant.components.proxmoxve.const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_VMS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_TEST_CONFIG

from tests.common import MockConfigEntry

MOCK_USER_STEP = {
    CONF_HOST: "127.0.0.1",
    CONF_USERNAME: "test_user@pam",
    CONF_PASSWORD: "test_password",
    CONF_VERIFY_SSL: True,
    CONF_PORT: 8006,
    CONF_REALM: "pam",
}

MOCK_USER_SETUP = {CONF_NODES: ["pve1"]}

MOCK_USER_FINAL = {
    **MOCK_USER_STEP,
    **MOCK_USER_SETUP,
}


async def test_form(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_STEP,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "127.0.0.1"
    assert result["data"] == MOCK_TEST_CONFIG


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (
            AuthenticationError("Invalid credentials"),
            "invalid_auth",
        ),
        (
            SSLError("SSL handshake failed"),
            "ssl_error",
        ),
        (
            ConnectTimeout("Connection timed out"),
            "connect_timeout",
        ),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all exceptions."""
    with patch(
        "homeassistant.components.proxmoxve.config_flow.ProxmoxAPI",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_STEP,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": reason}


async def test_form_no_nodes_exception(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
) -> None:
    """Test we handle no nodes found exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_proxmox_client.nodes.get.side_effect = ResourceException(
        "404", "status_message", "content"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_STEP,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_nodes_found"}


async def test_form_nodes_exception(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
) -> None:
    """Test we handle if an exception arises for retrieving VMs or containers."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    mock_proxmox_client._node_mock.qemu.get.side_effect = ResourceException(
        "404", "status_message", "content"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_STEP,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_nodes_found"}


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test we handle duplicate entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_USERNAME: "test_user@pam",
            CONF_PASSWORD: "test_password",
            CONF_VERIFY_SSL: True,
            CONF_PORT: 8006,
            CONF_REALM: "pam",
            CONF_NODES: [
                {
                    CONF_NODE: "pve1",
                    CONF_VMS: [100],
                    CONF_CONTAINERS: [200],
                }
            ],
        },
        unique_id="127.0.0.1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_STEP,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_proxmox_client,
) -> None:
    """Test importing from YAML creates a config entry and sets it up."""
    MOCK_IMPORT_CONFIG = {
        DOMAIN: {
            **MOCK_USER_STEP,
            **MOCK_USER_SETUP,
        }
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_IMPORT_CONFIG[DOMAIN]
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"nodes": ["pve1"]},
    )
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "127.0.0.1"
    assert result["data"][CONF_HOST] == "127.0.0.1"
    assert len(mock_setup_entry.mock_calls) == 1

    entry = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data[CONF_HOST] == "127.0.0.1"
    )
    assert entry.state is ConfigEntryState.LOADED
