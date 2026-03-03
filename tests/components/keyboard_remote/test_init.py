"""Tests for the Keyboard Remote integration init."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.keyboard_remote import _async_import_yaml_device
from homeassistant.components.keyboard_remote.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import FAKE_BY_ID_BASENAME, FAKE_DEVICE_NAME, FAKE_DEVICE_PATH

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_inotify():
    """Mock inotify to prevent real filesystem access."""
    with patch(
        "homeassistant.components.keyboard_remote.Inotify",
    ) as mock_cls:
        mock_instance = MagicMock()
        # Make async iteration raise StopAsyncIteration immediately
        mock_instance.__aiter__ = MagicMock(return_value=mock_instance)
        mock_instance.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_list_devices():
    """Mock evdev list_devices to return empty list."""
    with patch(
        "evdev.list_devices",
        return_value=[],
    ):
        yield


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up a config entry creates the shared manager."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert mock_config_entry.state.name == "LOADED"


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the last config entry removes the shared manager."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN not in hass.data


async def test_multiple_entries_shared_manager(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test multiple entries share one manager, cleanup on last unload."""
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        unique_id="usb-Other_Device-event-kbd",
        title="Other Device",
        data={
            "device_path": "/dev/input/by-id/usb-Other_Device-event-kbd",
            "device_name": "Other Device",
        },
        options=mock_config_entry.options.copy(),
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    manager = hass.data[DOMAIN]

    # Unload first entry — manager should still exist
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert hass.data[DOMAIN] is manager

    # Unload second entry — manager should be cleaned up
    await hass.config_entries.async_unload(entry2.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN not in hass.data


async def test_yaml_import_triggers_config_flow(hass: HomeAssistant) -> None:
    """Test that YAML config triggers import flow and creates deprecation issue."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        assert await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_descriptor": "/dev/input/event5"},
        )

    # Verify config entry was created
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data["device_path"] == FAKE_DEVICE_PATH


async def test_yaml_import_creates_deprecation_issue(
    hass: HomeAssistant,
) -> None:
    """Test YAML import creates a deprecation repair issue."""
    issue_registry = ir.async_get(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        await _async_import_yaml_device(
            hass, {"device_descriptor": "/dev/input/event5"}
        )

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )


async def test_yaml_import_failure_creates_issue(
    hass: HomeAssistant,
) -> None:
    """Test YAML import failure creates an error issue."""
    issue_registry = ir.async_get(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(None, None, None),
    ):
        await _async_import_yaml_device(hass, {})

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="deprecated_yaml_import_issue_cannot_identify_device",
    )
