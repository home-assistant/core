"""Tests for OPNsense config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components import opnsense
from homeassistant.components.opnsense import config_flow
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component


async def test_async_step_user_create_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User step creates an entry with normalized tracker interfaces."""
    monkeypatch.setattr(
        config_flow,
        "_async_validate_input",
        AsyncMock(
            return_value={
                CONF_URL: "https://router.local",
                CONF_API_KEY: "key",
                config_flow.CONF_API_SECRET: "secret",
                CONF_VERIFY_SSL: False,
                config_flow.CONF_TRACKER_INTERFACES: ["LAN", "OPT1"],
            }
        ),
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_URL: "https://router.local",
            CONF_API_KEY: "key",
            config_flow.CONF_API_SECRET: "secret",
            CONF_VERIFY_SSL: False,
            config_flow.CONF_TRACKER_INTERFACES: "LAN, OPT1",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "router.local"
    assert result["data"][config_flow.CONF_TRACKER_INTERFACES] == ["LAN", "OPT1"]


async def test_async_validate_input_normalizes_url_and_validates_interfaces(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validation normalizes URL and validates tracker interfaces."""
    interface_client = MagicMock()
    network_insight_client = MagicMock()

    network_insight_client.get_interfaces.return_value = {
        "igb0": "WAN",
        "igb1": "LAN",
        "igb2": "OPT1",
    }

    interface_client_factory = MagicMock(return_value=interface_client)
    network_insight_client_factory = MagicMock(return_value=network_insight_client)
    monkeypatch.setattr(
        config_flow.diagnostics, "InterfaceClient", interface_client_factory
    )
    monkeypatch.setattr(
        config_flow.diagnostics, "NetworkInsightClient", network_insight_client_factory
    )

    result = await config_flow._async_validate_input(
        hass,
        {
            CONF_URL: "router.local/api",
            CONF_API_KEY: "key",
            config_flow.CONF_API_SECRET: "secret",
            CONF_VERIFY_SSL: False,
            config_flow.CONF_TRACKER_INTERFACES: "LAN, LAN, OPT1",
        },
    )

    assert result[CONF_URL] == "https://router.local"
    assert result[config_flow.CONF_TRACKER_INTERFACES] == ["LAN", "OPT1"]

    interface_client_factory.assert_called_once_with(
        "key",
        "secret",
        "https://router.local",
        False,
        timeout=config_flow.CLIENT_TIMEOUT,
    )
    network_insight_client_factory.assert_called_once_with(
        "key",
        "secret",
        "https://router.local",
        False,
        timeout=config_flow.CLIENT_TIMEOUT,
    )
    interface_client.get_arp.assert_called_once_with()
    network_insight_client.get_interfaces.assert_called_once_with()


async def test_async_step_user_invalid_interface(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User step returns an error when tracker interface validation fails."""
    monkeypatch.setattr(
        config_flow,
        "_async_validate_input",
        AsyncMock(side_effect=config_flow.InvalidTrackerInterface),
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_URL: "https://router.local",
            CONF_API_KEY: "key",
            config_flow.CONF_API_SECRET: "secret",
            CONF_VERIFY_SSL: False,
            config_flow.CONF_TRACKER_INTERFACES: "LAN",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_tracker_interface"}


async def test_async_step_import_normalizes_interfaces(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Import step normalizes tracker interfaces and creates an entry."""
    monkeypatch.setattr(
        config_flow,
        "_async_validate_input",
        AsyncMock(
            return_value={
                CONF_URL: "https://router.local",
                CONF_API_KEY: "key",
                config_flow.CONF_API_SECRET: "secret",
                CONF_VERIFY_SSL: False,
                config_flow.CONF_TRACKER_INTERFACES: ["LAN", "OPT1"],
            }
        ),
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_URL: "https://router.local/",
            CONF_API_KEY: "key",
            config_flow.CONF_API_SECRET: "secret",
            CONF_VERIFY_SSL: False,
            config_flow.CONF_TRACKER_INTERFACES: ["LAN", "LAN", "OPT1"],
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][config_flow.CONF_TRACKER_INTERFACES] == ["LAN", "OPT1"]


async def test_async_setup_yaml_import_creates_deprecated_yaml_issue(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """YAML import creates deprecated YAML repair issue on success."""
    async_init_mock = AsyncMock(return_value={"type": FlowResultType.CREATE_ENTRY})
    create_issue_mock = MagicMock()

    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init_mock)
    monkeypatch.setattr(opnsense.ir, "async_create_issue", create_issue_mock)

    result = await async_setup_component(
        hass,
        opnsense.DOMAIN,
        {
            opnsense.DOMAIN: {
                CONF_URL: "https://router.local",
                CONF_API_KEY: "key",
                opnsense.CONF_API_SECRET: "secret",
                CONF_VERIFY_SSL: False,
                opnsense.CONF_TRACKER_INTERFACES: ["LAN"],
            }
        },
    )
    await hass.async_block_till_done()

    assert result
    assert async_init_mock.call_count == 1
    create_issue_mock.assert_called_once()
