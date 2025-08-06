"""Test Wallbox Init Component."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.input_number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import http_403_error, http_429_error, setup_integration
from .const import (
    MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
    WALLBOX_STATUS_RESPONSE_NO_POWER_BOOST,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_wallbox_setup_unload_entry(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox Unload."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_unload_entry_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox Unload Connection Error."""
    with patch.object(mock_wallbox, "authenticate", side_effect=http_403_error):
        await setup_integration(hass, entry)
        assert entry.state is ConfigEntryState.SETUP_ERROR

        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error_too_many_requests(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with connection error."""

    with patch.object(mock_wallbox, "getChargerStatus", side_effect=http_429_error):
        await setup_integration(hass, entry)
        assert entry.state is ConfigEntryState.SETUP_RETRY

        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_error_auth(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_wallbox,
) -> None:
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with (
        patch.object(mock_wallbox, "authenticate", side_effect=http_403_error),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                ATTR_VALUE: 1.1,
            },
            blocking=True,
        )

    with (
        patch.object(mock_wallbox, "authenticate", side_effect=http_429_error),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                ATTR_VALUE: 1.1,
            },
            blocking=True,
        )

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_http_error(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with authentication error."""

    with patch.object(mock_wallbox, "getChargerStatus", side_effect=http_403_error):
        await setup_integration(hass, entry)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_too_many_requests(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(mock_wallbox, "getChargerStatus", side_effect=http_429_error):
        async_fire_time_changed(hass, datetime.now() + timedelta(seconds=120), True)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with connection error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(mock_wallbox, "pauseChargingSession", side_effect=http_403_error):
        async_fire_time_changed(hass, datetime.now() + timedelta(seconds=120), True)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_setup_load_entry_no_eco_mode(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox Unload."""
    with patch.object(
        mock_wallbox,
        "getChargerStatus",
        return_value=WALLBOX_STATUS_RESPONSE_NO_POWER_BOOST,
    ):
        await setup_integration(hass, entry)
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED
