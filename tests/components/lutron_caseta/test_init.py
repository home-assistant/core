"""Tests for the Lutron Caseta integration."""

import ssl
from typing import Any
from unittest.mock import patch

from pylutron_caseta.smartbridge import Smartbridge
import pytest

from homeassistant.components import lutron_caseta
from homeassistant.components.lutron_caseta.const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    issue_registry as ir,
    translation,
)
from homeassistant.setup import async_setup_component

from . import MockBridge, async_setup_integration, make_mock_entry


@pytest.mark.parametrize(
    ("constant", "message", "timeout_during_connect", "timeout_during_configure"),
    [
        ("CONNECT_TIMEOUT", "Timed out on connect", True, False),
        ("CONFIGURE_TIMEOUT", "Timed out on configure", False, True),
    ],
)
async def test_timeout_during_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    constant: str,
    message: str,
    timeout_during_connect: bool,
    timeout_during_configure: bool,
) -> None:
    """Test a timeout during setup."""
    mock_entry = make_mock_entry()
    mock_entry.add_to_hass(hass)
    with patch.object(lutron_caseta, constant, 0.001):
        await async_setup_integration(
            hass,
            MockBridge,
            config_entry_id=mock_entry.entry_id,
            timeout_during_connect=timeout_during_connect,
            timeout_during_configure=timeout_during_configure,
        )
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
    assert f"{message} for 1.1.1.1" in caplog.text


async def test_cannot_connect(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test failing to connect."""
    mock_entry = make_mock_entry()
    mock_entry.add_to_hass(hass)
    await async_setup_integration(
        hass, MockBridge, config_entry_id=mock_entry.entry_id, can_connect=False
    )
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Connection failed to 1.1.1.1" in caplog.text


async def test_invalid_certificate(hass: HomeAssistant) -> None:
    """Test setup fails with an invalid certificate."""
    mock_entry = make_mock_entry()
    mock_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.lutron_caseta.Smartbridge.create_tls",
        side_effect=ssl.SSLError,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        mock_entry.reason == "Invalid certificate used to connect to bridge at 1.1.1.1"
    )


async def test_keypad_device_via_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test the keypad device is linked to the bridge device via via_device_id."""
    mock_entry = await async_setup_integration(hass, MockBridge)

    bridge_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, 1234), mock_entry.entry_id
    )
    keypad_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, 66286451), mock_entry.entry_id
    )

    assert bridge_device is not None
    assert keypad_device is not None
    assert keypad_device.via_device_id == bridge_device.id
    assert bridge_device.via_device_id is None


@pytest.mark.parametrize(
    ("host", "can_connect", "issue_domain", "issue_id"),
    [
        pytest.param(
            "2.2.2.2",
            True,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            id="imported",
        ),
        pytest.param(
            "1.1.1.1",
            True,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            id="already_configured",
        ),
        pytest.param(
            "2.2.2.2",
            False,
            DOMAIN,
            "deprecated_yaml_import_issue_cannot_connect",
            id="cannot_connect",
        ),
    ],
)
async def test_yaml_import_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    host: str,
    can_connect: bool,
    issue_domain: str,
    issue_id: str,
) -> None:
    """Test importing YAML creates the matching deprecation issue."""
    # The existing entry uses host 1.1.1.1, so importing that host aborts.
    make_mock_entry().add_to_hass(hass)

    with (
        patch.object(
            Smartbridge, "create_tls", return_value=MockBridge(can_connect=can_connect)
        ),
        patch(
            "homeassistant.components.lutron_caseta.async_setup_entry",
            return_value=True,
        ),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_HOST: host,
                    CONF_KEYFILE: "",
                    CONF_CERTFILE: "",
                    CONF_CA_CERTS: "",
                }
            },
        )
        await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(issue_domain, issue_id)
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.issue_domain == DOMAIN
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "Lutron Caséta",
    }


async def test_yaml_import_partial_failure(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a failed bridge import prevents the remove-your-YAML issue."""
    bridges = {
        "2.2.2.2": MockBridge(can_connect=True),
        "3.3.3.3": MockBridge(can_connect=False),
    }
    yaml_bridges = [
        {CONF_HOST: host, CONF_KEYFILE: "", CONF_CERTFILE: "", CONF_CA_CERTS: ""}
        for host in bridges
    ]

    with (
        patch.object(
            Smartbridge,
            "create_tls",
            side_effect=lambda hostname, *args, **kwargs: bridges[hostname],
        ),
        patch(
            "homeassistant.components.lutron_caseta.async_setup_entry",
            return_value=True,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: yaml_bridges})
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert len(issue_registry.issues) == 1


async def test_yaml_import_finishes_before_setup_returns(hass: HomeAssistant) -> None:
    """Test all YAML bridges are imported before the integration setup returns."""
    await translation.async_load_integrations(hass, {DOMAIN})
    serials = {"2.2.2.2": 2222, "3.3.3.3": 3333}
    yaml_bridges = [
        {CONF_HOST: host, CONF_KEYFILE: "", CONF_CERTFILE: "", CONF_CA_CERTS: ""}
        for host in serials
    ]

    def create_bridge(hostname: str, **kwargs: Any) -> MockBridge:
        bridge = MockBridge(can_connect=True)
        bridge.devices["1"]["serial"] = serials[hostname]
        return bridge

    with (
        patch.object(
            Smartbridge,
            "create_tls",
            side_effect=create_bridge,
        ),
        patch(
            "homeassistant.components.lutron_caseta.async_setup_entry",
            return_value=True,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: yaml_bridges})

        assert len(hass.config_entries.async_entries(DOMAIN)) == 2
