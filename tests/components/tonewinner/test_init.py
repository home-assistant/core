"""Test the Tonewinner integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.tonewinner.const import CONF_SERIAL_PORT, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
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
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is mock_receiver
    mock_receiver.connect.assert_awaited_once()
    mock_receiver.query_state.assert_awaited_once()
    mock_receiver.disconnect.assert_not_awaited()


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test a failed connection raises ConfigEntryNotReady and cleans up."""
    mock_config_entry.add_to_hass(hass)
    mock_receiver.connect.side_effect = OSError("Permission denied")

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
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_receiver.disconnect.assert_awaited_once()


async def test_setup_entry_multiple_times(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test that setting up multiple entries doesn't conflict."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0", CONF_MODEL: "AT-500"},
        entry_id="test_entry_id_1",
        title="AT-500",
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB1", CONF_MODEL: "AT-500"},
        entry_id="test_entry_id_2",
        title="AT-500",
    )

    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    mock_receiver2 = MagicMock()
    mock_receiver2.connect = AsyncMock()
    mock_receiver2.query_state = AsyncMock()
    mock_receiver2.disconnect = AsyncMock()

    def receiver_factory(*args: str, **kwargs: int) -> MagicMock:
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
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test unloading the integration disconnects the receiver."""
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
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ):
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    mock_receiver.disconnect.assert_awaited_once()


async def test_unload_entry_platform_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test unload keeps the receiver connected when platforms fail to unload."""
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
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)

    mock_receiver.disconnect.assert_not_awaited()
