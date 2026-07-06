"""Tests for integration setup and unload."""

from typing import Any, cast
from unittest.mock import Mock

from besen.exceptions import CannotConnect, InvalidAuth
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import FIXTURE_ADDRESS, BesenClientFixture

from tests.common import MockConfigEntry


def _assert_entry_state(entry: MockConfigEntry, state: ConfigEntryState) -> None:
    """Assert a config entry state without narrowing later assertions."""

    assert entry.state is state


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
) -> None:
    """Test setup creates runtime data and forwards the switch platform."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is True
    await hass.async_block_till_done()

    _assert_entry_state(mock_config_entry, ConfigEntryState.LOADED)
    assert cast(Any, mock_config_entry.runtime_data).client is mock_besen_client.client
    assert mock_besen_client.constructor.call_args.kwargs["address"] == FIXTURE_ADDRESS
    mock_besen_client.client.async_start.assert_awaited_once()
    assert hass.states.get("switch.garage_charge") is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id) is True
    await hass.async_block_till_done()

    _assert_entry_state(mock_config_entry, ConfigEntryState.NOT_LOADED)
    mock_besen_client.remove_listener.assert_called_once()
    mock_besen_client.client.async_stop.assert_awaited_once()


async def test_setup_entry_no_connectable_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
    mock_ble_device: Mock,
) -> None:
    """Test setup retries when no active Bluetooth path exists."""

    mock_ble_device.return_value = None
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    _assert_entry_state(mock_config_entry, ConfigEntryState.SETUP_RETRY)
    mock_besen_client.constructor.assert_not_called()


async def test_setup_entry_auth_error_fails_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
) -> None:
    """Test setup maps invalid auth to a config-entry auth failure."""

    mock_besen_client.client.async_start.side_effect = InvalidAuth("bad pin")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    _assert_entry_state(mock_config_entry, ConfigEntryState.SETUP_ERROR)
    mock_besen_client.remove_listener.assert_called_once()
    mock_besen_client.client.async_stop.assert_awaited_once()


async def test_setup_entry_connect_error_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
) -> None:
    """Test setup maps connection errors to a retry."""

    mock_besen_client.client.async_start.side_effect = CannotConnect("offline")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    _assert_entry_state(mock_config_entry, ConfigEntryState.SETUP_RETRY)
    mock_besen_client.remove_listener.assert_called_once()
    mock_besen_client.client.async_stop.assert_awaited_once()


async def test_unload_skips_shutdown_when_platform_unload_fails(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
) -> None:
    """Test unload does not stop the client when platform unload fails."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is True
    await hass.async_block_till_done()

    async def _async_unload_platforms(*args: Any, **kwargs: Any) -> bool:
        """Return a failed platform unload."""

        return False

    monkeypatch.setattr(
        hass.config_entries,
        "async_unload_platforms",
        _async_unload_platforms,
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id) is False

    mock_besen_client.remove_listener.assert_not_called()
    mock_besen_client.client.async_stop.assert_not_awaited()
