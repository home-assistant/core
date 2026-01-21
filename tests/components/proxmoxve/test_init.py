"""Tests for the Proxmox VE integration initialization."""

from unittest.mock import MagicMock

from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import pytest
import requests
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.proxmoxve.const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry


async def test_config_import(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_setup_entry: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test sensor initialization."""
    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    CONF_HOST: "127.0.0.1",
                    CONF_PORT: 8006,
                    CONF_REALM: "pam",
                    CONF_USERNAME: "test_user@pam",
                    CONF_PASSWORD: "test_password",
                    CONF_VERIFY_SSL: True,
                    CONF_NODES: [
                        {
                            CONF_NODE: "pve1",
                            CONF_VMS: [100, 101],
                            CONF_CONTAINERS: [200, 201],
                        },
                    ],
                }
            ]
        },
    )

    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    assert (HOMEASSISTANT_DOMAIN, "deprecated_yaml") in issue_registry.issues
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (
            AuthenticationError("Invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            SSLError("SSL handshake failed"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (ConnectTimeout("Connection timed out"), ConfigEntryState.SETUP_RETRY),
        (
            ResourceException,
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            requests.exceptions.ConnectionError,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=[
        "auth_error",
        "ssl_error",
        "connect_timeout",
        "resource_exception",
        "connection_error",
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the _async_setup."""
    mock_proxmox_client.nodes.get.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == expected_state
