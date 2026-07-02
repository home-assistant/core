"""Tests for the AquaLogic integration setup."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aqualogic.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_processor: MagicMock,
) -> None:
    """Test loading and unloading the config entry starts and stops the processor."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_processor.start.assert_called_once()

    mock_processor.is_alive.return_value = False
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_processor.shutdown.assert_called_once()
    mock_processor.join.assert_called_once_with(timeout=5)


@pytest.mark.usefixtures("mock_aqualogic_device")
async def test_import_from_yaml(
    hass: HomeAssistant,
    mock_processor: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing from YAML creates a config entry and a deprecation issue."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.issue_domain == DOMAIN


async def test_import_from_yaml_cannot_connect(
    hass: HomeAssistant,
    mock_processor: MagicMock,
    mock_aqualogic_device: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed YAML import raises a specific issue instead of the migration notice."""
    mock_aqualogic_device.return_value.connect.side_effect = OSError
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}},
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []

    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is None
    )

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue is not None
    assert issue.issue_domain == DOMAIN


async def test_processor_run_exits_on_shutdown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test run() processes once then exits when shutdown is already set."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.aqualogic.AquaLogic") as mock_aqualogic,
        patch("homeassistant.components.aqualogic.PLATFORMS", []),
        patch("homeassistant.components.aqualogic.AquaLogicProcessor.start"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        processor = mock_config_entry.runtime_data
        processor._shutdown = True
        processor.run()
    mock_aqualogic.return_value.connect.assert_called_once_with("1.2.3.4", 8899)


async def test_processor_run_reconnects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the processor reconnects after a dropped connection."""
    mock_config_entry.add_to_hass(hass)
    connect_calls = 0

    with (
        patch("homeassistant.components.aqualogic.RECONNECT_INTERVAL", timedelta(0)),
        patch("homeassistant.components.aqualogic.AquaLogic") as mock_al,
        patch("homeassistant.components.aqualogic.PLATFORMS", []),
        patch("homeassistant.components.aqualogic.AquaLogicProcessor.start"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        processor = mock_config_entry.runtime_data

        def stop_on_second_connect(*args: object, **kwargs: object) -> None:
            nonlocal connect_calls
            connect_calls += 1
            if connect_calls >= 2:
                processor._shutdown = True

        mock_al.return_value.connect.side_effect = stop_on_second_connect
        processor.run()

    assert connect_calls == 2
