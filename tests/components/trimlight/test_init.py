"""Tests for Trimlight config entry setup and unloading."""

from unittest.mock import MagicMock

from aiotrimlight import TrimlightConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.trimlight.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import DID, ENTITY_ID, NAME

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test initial reads, device registration, and unloading."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_trimlight.get_device_info.assert_awaited_once_with()
    mock_trimlight.get_light_state.assert_awaited_once_with()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("method", "translation_key"),
    [
        pytest.param("get_device_info", "setup_failed", id="device-info"),
        pytest.param("get_light_state", "update_failed", id="first-state"),
    ],
)
async def test_setup_error_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
    method: str,
    translation_key: str,
) -> None:
    """Test unavailable controllers retry setup and can subsequently load."""
    mock_method = getattr(mock_trimlight, method)
    mock_method.side_effect = TrimlightConnectionError("connection failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders == {
        "error": "connection failed",
        "name": NAME,
    }

    mock_method.side_effect = None
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
