"""Tests for OPNsense config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components import opnsense
from homeassistant.components.opnsense import config_flow
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("raw_url", "normalized_url"),
    [
        ("router.local/api", "https://router.local"),
        ("  HTTPS://Router.Local/  ", "https://router.local"),
        ("https://router.local", "https://router.local"),
        ("https://router.local:8443/api/v1?x=1#top", "https://router.local:8443"),
    ],
)
def test_normalize_url_compatibility(raw_url: str, normalized_url: str) -> None:
    """Normalize URL keeps previous canonical unique-id output."""
    assert config_flow._normalize_url(raw_url) == normalized_url


def test_normalize_url_invalid() -> None:
    """Normalize URL raises when URL cannot produce a host."""
    with pytest.raises(config_flow.InvalidURL):
        config_flow._normalize_url("https:///api")


def test_normalize_tracker_interfaces_non_string() -> None:
    """Normalize tracker interfaces returns empty list for invalid type."""
    assert config_flow._normalize_tracker_interfaces(None) == []


def test_tracker_interfaces_default_with_invalid_type() -> None:
    """Tracker interfaces default returns empty string for invalid type."""
    assert (
        config_flow._tracker_interfaces_default(
            {config_flow.CONF_TRACKER_INTERFACES: 123}
        )
        == ""
    )


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


async def test_async_step_user_cannot_connect(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User step returns cannot_connect when validation fails to connect."""
    monkeypatch.setattr(
        config_flow,
        "_async_validate_input",
        AsyncMock(side_effect=config_flow.CannotConnect),
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_URL: "https://router.local",
            CONF_API_KEY: "key",
            config_flow.CONF_API_SECRET: "secret",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


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


async def test_async_validate_input_cannot_connect_on_interface_client_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validation raises CannotConnect when ARP request fails."""
    interface_client = MagicMock()
    interface_client.get_arp.side_effect = config_flow.RequestException(
        "Connection failed"
    )
    monkeypatch.setattr(
        config_flow.diagnostics,
        "InterfaceClient",
        MagicMock(return_value=interface_client),
    )

    with pytest.raises(config_flow.CannotConnect):
        await config_flow._async_validate_input(
            hass,
            {
                CONF_URL: "https://router.local",
                CONF_API_KEY: "key",
                config_flow.CONF_API_SECRET: "secret",
                CONF_VERIFY_SSL: False,
            },
        )


async def test_async_validate_input_cannot_connect_on_interface_validation_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validation raises CannotConnect when interface lookup fails."""
    interface_client = MagicMock()
    interface_client.get_arp.return_value = []
    network_insight_client = MagicMock()
    network_insight_client.get_interfaces.side_effect = config_flow.APIException(
        status_code=500, resp_body="Internal Server Error"
    )

    monkeypatch.setattr(
        config_flow.diagnostics,
        "InterfaceClient",
        MagicMock(return_value=interface_client),
    )
    monkeypatch.setattr(
        config_flow.diagnostics,
        "NetworkInsightClient",
        MagicMock(return_value=network_insight_client),
    )

    with pytest.raises(config_flow.CannotConnect):
        await config_flow._async_validate_input(
            hass,
            {
                CONF_URL: "https://router.local",
                CONF_API_KEY: "key",
                config_flow.CONF_API_SECRET: "secret",
                CONF_VERIFY_SSL: False,
                config_flow.CONF_TRACKER_INTERFACES: ["LAN"],
            },
        )


async def test_async_validate_input_invalid_tracker_interface(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validation raises InvalidTrackerInterface for unknown interface."""
    interface_client = MagicMock()
    interface_client.get_arp.return_value = []
    network_insight_client = MagicMock()
    network_insight_client.get_interfaces.return_value = {"igb0": "WAN"}

    monkeypatch.setattr(
        config_flow.diagnostics,
        "InterfaceClient",
        MagicMock(return_value=interface_client),
    )
    monkeypatch.setattr(
        config_flow.diagnostics,
        "NetworkInsightClient",
        MagicMock(return_value=network_insight_client),
    )

    with pytest.raises(config_flow.InvalidTrackerInterface):
        await config_flow._async_validate_input(
            hass,
            {
                CONF_URL: "https://router.local",
                CONF_API_KEY: "key",
                config_flow.CONF_API_SECRET: "secret",
                CONF_VERIFY_SSL: False,
                config_flow.CONF_TRACKER_INTERFACES: ["LAN"],
            },
        )


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


async def test_async_setup_yaml_import_create_issue_on_init_exception(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """YAML import creates error issue when config flow init raises."""
    async_init_mock = AsyncMock(side_effect=Exception("boom"))
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
            }
        },
    )
    await hass.async_block_till_done()

    assert result
    create_issue_mock.assert_called_once()
    assert create_issue_mock.call_args.args[0] is hass
    assert create_issue_mock.call_args.args[1] == opnsense.DOMAIN


async def test_async_setup_yaml_import_create_issue_on_abort_not_already_configured(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """YAML import creates error issue on abort with non-configured reason."""
    async_init_mock = AsyncMock(
        return_value={"type": FlowResultType.ABORT, "reason": "invalid_auth"}
    )
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
            }
        },
    )
    await hass.async_block_till_done()

    assert result
    create_issue_mock.assert_called_once()


async def test_async_setup_yaml_import_no_issue_if_flow_not_finished(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """YAML import does not create issue if flow did not finish."""
    async_init_mock = AsyncMock(return_value={"type": FlowResultType.FORM})
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
            }
        },
    )
    await hass.async_block_till_done()

    assert result
    create_issue_mock.assert_not_called()


async def test_async_step_reauth_confirm_success(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reauth confirm updates entry and reloads it on success."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            CONF_URL: "https://router.local",
            CONF_API_KEY: "old",
            config_flow.CONF_API_SECRET: "old_secret",
            CONF_VERIFY_SSL: False,
        },
    )
    entry.add_to_hass(hass)

    monkeypatch.setattr(
        config_flow,
        "_async_validate_input",
        AsyncMock(
            return_value={
                CONF_URL: "https://router.local",
                CONF_API_KEY: "new",
                config_flow.CONF_API_SECRET: "new_secret",
                CONF_VERIFY_SSL: False,
                config_flow.CONF_TRACKER_INTERFACES: [],
            }
        ),
    )
    reload_entry = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload_entry)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data={},
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "new",
            config_flow.CONF_API_SECRET: "new_secret",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    reload_entry.assert_called_once_with(entry.entry_id)
