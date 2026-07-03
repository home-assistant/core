"""Tests for the KEBA charging station integration setup."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.keba.const import (
    CONF_FS_FALLBACK,
    CONF_FS_PERSIST,
    CONF_FS_TIMEOUT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import ENTRY_DATA

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_keba: MagicMock,
) -> None:
    """Test successful config entry setup."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is mock_keba
    mock_keba.start_periodic_request.assert_called_once()


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_keba: MagicMock,
) -> None:
    """Test config entry setup when the charger is not reachable."""
    mock_keba.setup.return_value = False

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_connection_oserror(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_keba: MagicMock,
) -> None:
    """Test config entry setup when an OSError is raised."""
    mock_keba.setup.side_effect = OSError("connection refused")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_failsafe_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_keba: MagicMock,
) -> None:
    """Test that a ValueError from set_failsafe logs a warning but succeeds."""
    mock_keba.set_failsafe.side_effect = ValueError("invalid values")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_with_failsafe_enabled(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test config entry setup with failsafe mode enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **ENTRY_DATA,
            "failsafe": True,
            CONF_FS_TIMEOUT: 60,
            CONF_FS_FALLBACK: 8.0,
            CONF_FS_PERSIST: 1,
        },
        unique_id="12345678",
    )
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    mock_keba.set_failsafe.assert_called_once_with(60, 8.0, True)


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_keba: MagicMock,
) -> None:
    """Test unloading the KEBA config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    mock_keba.stop_periodic_request.assert_called_once()


async def test_async_setup_registers_services(hass: HomeAssistant) -> None:
    """Test that async_setup registers all expected services."""
    result = await async_setup_component(hass, DOMAIN, {})
    assert result is True

    for service in (
        "request_data",
        "set_energy",
        "set_current",
        "authorize",
        "deauthorize",
        "enable",
        "disable",
        "set_failsafe",
    ):
        assert hass.services.has_service(DOMAIN, service)


async def test_service_call_no_entries_is_noop(hass: HomeAssistant) -> None:
    """Test that a service call with no configured entries is a silent no-op."""
    await async_setup_component(hass, DOMAIN, {})
    # No integration entry exists - calling any service must not raise
    await hass.services.async_call(DOMAIN, "request_data", {}, blocking=True)


@pytest.mark.parametrize(
    "yaml_config",
    [
        pytest.param(ENTRY_DATA, id="plain"),
        pytest.param({**ENTRY_DATA, "refresh_interval": 10}, id="removed_option"),
    ],
)
async def test_async_setup_with_yaml_triggers_import(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    issue_registry: ir.IssueRegistry,
    yaml_config: dict[str, Any],
) -> None:
    """Test that YAML config creates a deprecated issue and triggers an import flow."""
    with (
        patch(
            "homeassistant.components.keba.config_flow.KebaHandler",
            return_value=mock_keba,
        ),
        patch(
            "homeassistant.components.keba.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: yaml_config})
        assert result is True
        await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is not None
    )


@pytest.mark.parametrize(
    ("setup_side_effect", "setup_return_value", "issue_id"),
    [
        pytest.param(
            None, False, "deprecated_yaml_import_issue_cannot_connect", id="no_response"
        ),
        pytest.param(
            Exception("unexpected error"),
            True,
            "deprecated_yaml_import_issue_unknown",
            id="unexpected",
        ),
    ],
)
async def test_async_setup_with_yaml_import_fails(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    issue_registry: ir.IssueRegistry,
    setup_side_effect: Exception | None,
    setup_return_value: bool,
    issue_id: str,
) -> None:
    """Test that a failed YAML import creates an import issue instead."""
    mock_keba.setup.side_effect = setup_side_effect
    mock_keba.setup.return_value = setup_return_value

    with patch(
        "homeassistant.components.keba.config_flow.KebaHandler",
        return_value=mock_keba,
    ):
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: ENTRY_DATA})
        assert result is True
        await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is None
    )
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


async def test_async_setup_with_yaml_and_existing_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_keba: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that YAML config next to an existing entry creates the deprecated issue."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.keba.config_flow.KebaHandler",
        return_value=mock_keba,
    ):
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: ENTRY_DATA})
        assert result is True
        await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is not None
    )


@pytest.mark.usefixtures("init_integration")
async def test_service_request_data(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test the request_data service call."""
    await hass.services.async_call(DOMAIN, "request_data", {}, blocking=True)
    mock_keba.async_request_data.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_service_set_energy(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test the set_energy service call."""
    await hass.services.async_call(
        DOMAIN, "set_energy", {"energy": 10.0}, blocking=True
    )
    mock_keba.async_set_energy.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_service_set_current(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test the set_current service call."""
    await hass.services.async_call(
        DOMAIN, "set_current", {"current": 16.0}, blocking=True
    )
    mock_keba.async_set_current.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_service_authorize(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test the authorize service call."""
    await hass.services.async_call(DOMAIN, "authorize", {}, blocking=True)
    mock_keba.async_start.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_service_deauthorize(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test the deauthorize service call."""
    await hass.services.async_call(DOMAIN, "deauthorize", {}, blocking=True)
    mock_keba.async_stop.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_service_enable_deprecated(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the deprecated enable service creates an issue."""
    await hass.services.async_call(DOMAIN, "enable", {}, blocking=True)
    mock_keba.async_enable_ev.assert_called_once()
    assert (
        issue_registry.async_get_issue(DOMAIN, "deprecated_service_enable") is not None
    )


@pytest.mark.usefixtures("init_integration")
async def test_service_disable_deprecated(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the deprecated disable service creates an issue."""
    await hass.services.async_call(DOMAIN, "disable", {}, blocking=True)
    mock_keba.async_disable_ev.assert_called_once()
    assert (
        issue_registry.async_get_issue(DOMAIN, "deprecated_service_disable") is not None
    )


@pytest.mark.usefixtures("init_integration")
async def test_service_set_failsafe(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test the set_failsafe service call."""
    await hass.services.async_call(
        DOMAIN,
        "set_failsafe",
        {CONF_FS_TIMEOUT: 30, CONF_FS_FALLBACK: 6.0, CONF_FS_PERSIST: 0},
        blocking=True,
    )
    mock_keba.async_set_failsafe.assert_called_once()
