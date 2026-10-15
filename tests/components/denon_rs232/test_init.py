"""Tests for the Denon RS-232 integration init."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.denon_rs232.config_flow import CONF_MODEL_NAME
from homeassistant.components.denon_rs232.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_MODEL
from homeassistant.core import HomeAssistant

from . import MOCK_MODEL
from .conftest import MockReceiver

from tests.common import MockConfigEntry


async def test_remove_entry_while_loaded(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    init_components: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a config entry does not schedule a reload.

    When removing a loaded entry, disconnect() fires the subscriber callback
    with state=None. The callback must not schedule a reload because the entry
    is already being removed (state is no longer LOADED).
    """

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entry should be fully removed without errors from the disconnect callback.
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_receiver.disconnect.assert_awaited_once()


async def test_setup_retry_hides_api_key(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    mock_usb_component: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setup retry message does not show the ESPHome API key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE: "esphome://proxy.local:6053/?port_name=RS232&key=SECRET",
            CONF_MODEL: MOCK_MODEL,
            CONF_MODEL_NAME: "AVR-3805",
        },
        title="AVR-3805",
    )
    entry.add_to_hass(hass)
    mock_receiver.connect.side_effect = ConnectionError("No response")

    with patch(
        "homeassistant.components.denon_rs232.DenonReceiver",
        return_value=mock_receiver,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.reason == (
        "Error connecting to Denon receiver at esphome://proxy.local:6053/"
    )
    assert "SECRET" not in caplog.text
