"""Test the Tonewinner AT-500 integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.tonewinner import async_update_options
from homeassistant.components.tonewinner.const import (
    CONF_BAUD_RATE,
    CONF_SERIAL_PORT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MagicMock, mock_receiver: MagicMock
) -> None:
    """Test setting up the integration."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.tonewinner.TonewinnerReceiver",
            return_value=mock_receiver,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.runtime_data is mock_receiver
    mock_receiver.connect.assert_called_once()
    mock_receiver.query_state.assert_called_once()


async def test_setup_entry_multiple_times(
    hass: HomeAssistant, mock_receiver: MagicMock
) -> None:
    """Test that setting up multiple entries doesn't conflict."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id_1",
        title="Tonewinner AT-500",
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB1",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id_2",
        title="Tonewinner AT-500",
    )

    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    mock_receiver2 = MagicMock()
    mock_receiver2.connect = AsyncMock()
    mock_receiver2.query_state = AsyncMock()
    mock_receiver2.disconnect = AsyncMock()

    def receiver_factory(*args, **kwargs):
        if args[0] == "/dev/ttyUSB1":
            return mock_receiver2
        return mock_receiver

    with (
        patch(
            "homeassistant.components.tonewinner.TonewinnerReceiver",
            side_effect=receiver_factory,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
    ):
        # Setting up one entry loads every entry of the integration
        assert await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()

        assert entry1.state is ConfigEntryState.LOADED
        assert entry2.state is ConfigEntryState.LOADED

    assert entry1.runtime_data is mock_receiver
    assert entry2.runtime_data is mock_receiver2


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MagicMock, mock_receiver: MagicMock
) -> None:
    """Test unloading the integration."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.tonewinner.TonewinnerReceiver",
            return_value=mock_receiver,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=True,
    ):
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    mock_receiver.disconnect.assert_called_once()


async def test_update_options(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test updating options triggers reload."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
    ) as mock_reload:
        await async_update_options(hass, mock_config_entry)

        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_unload_entry_without_runtime_data(
    hass: HomeAssistant, mock_config_entry: MagicMock, mock_receiver: MagicMock
) -> None:
    """Test unloading when runtime_data is None."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    mock_config_entry.runtime_data = None

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=True,
    ):
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
