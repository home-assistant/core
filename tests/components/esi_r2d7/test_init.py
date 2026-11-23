"""Tests for the ESI R2D7 integration setup."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from serialx import SerialException

from homeassistant.components.esi_r2d7.const import (
    CONF_FIRST_CHANNEL,
    CONF_LAST_CHANNEL,
    CONF_SYSTEM,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from .conftest import MockConnection


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test the entry loads, then unloads and closes the port."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_connection.connect.assert_awaited_once()

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    mock_connection.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    "exception",
    [OSError("No such device"), TimeoutError, SerialException("Proxy unavailable")],
)
async def test_setup_retry_hides_api_key(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
) -> None:
    """Test a port that cannot open retries setup without showing the API key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE: "esphome://proxy.local:6053/?port_name=RS232&key=SECRET",
            CONF_SYSTEM: 1,
            CONF_FIRST_CHANNEL: 1,
            CONF_LAST_CHANNEL: 3,
        },
    )
    entry.add_to_hass(hass)
    mock_connection.connect.side_effect = exception

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.reason == (
        "Error connecting to the ESI R2D7 at esphome://proxy.local:6053/"
    )
    assert "SECRET" not in caplog.text


async def test_link_loss_reloads_entry(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a lost serial link schedules a reload."""
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        mock_connection.mock_link(False)

    reload.assert_called_once_with(init_integration.entry_id)


async def test_remove_entry_while_loaded(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test removing a loaded entry does not schedule a reload."""
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await hass.config_entries.async_remove(init_integration.entry_id)
        await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    mock_connection.disconnect.assert_awaited_once()
    reload.assert_not_called()
