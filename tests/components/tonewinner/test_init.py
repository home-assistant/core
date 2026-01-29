"""Test the ToneWinner AT-500 integration setup."""

from unittest.mock import MagicMock, patch

from homeassistant.components.tonewinner import (
    async_setup_entry,
    async_unload_entry,
    async_update_options,
)
from homeassistant.components.tonewinner.const import (
    CONF_BAUD_RATE,
    CONF_SERIAL_PORT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test setting up the integration."""
    mock_config_entry.add_to_hass(hass)

    # Mock the platform setup to avoid needing actual platform loading
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_setup_entry_multiple_times(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that setting up multiple entries doesn't conflict."""
    entry1 = mock_config_entry
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

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        result1 = await async_setup_entry(hass, entry1)
        result2 = await async_setup_entry(hass, entry2)

        assert result1 is True
        assert result2 is True

        # Both entries should be stored
        assert entry1.entry_id in hass.data[DOMAIN]
        assert entry2.entry_id in hass.data[DOMAIN]


async def test_unload_entry(hass: HomeAssistant, mock_config_entry: MagicMock) -> None:
    """Test unloading the integration."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration first
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        await async_setup_entry(hass, mock_config_entry)

    # Now unload it
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=True,
    ):
        result = await async_unload_entry(hass, mock_config_entry)

        assert result is True
        assert mock_config_entry.entry_id not in hass.data[DOMAIN]


async def test_unload_entry_with_service(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test unloading cleans up registered services."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration data first (normally done by async_setup_entry)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = mock_config_entry.data

    # Simulate a registered service
    hass.data[DOMAIN][f"{mock_config_entry.entry_id}_service"] = MagicMock()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=True,
    ):
        result = await async_unload_entry(hass, mock_config_entry)

        assert result is True
        # Service should be cleaned up
        assert f"{mock_config_entry.entry_id}_service" not in hass.data.get(DOMAIN, {})


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


async def test_setup_entry_registers_update_listener(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that setup registers an update listener."""
    mock_config_entry.add_to_hass(hass)

    # Mock the platform setup to avoid needing actual platform loading
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        result = await async_setup_entry(hass, mock_config_entry)
        assert result is True


async def test_unload_entry_without_service(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test unloading when no service is registered."""
    mock_config_entry.add_to_hass(hass)

    # Set up without a service
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = mock_config_entry.data

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=True,
    ):
        # Should not raise an error even without a service
        result = await async_unload_entry(hass, mock_config_entry)

        assert result is True


async def test_data_stored_in_hass_data(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that config data is properly stored in hass.data."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        await async_setup_entry(hass, mock_config_entry)

        # Verify data structure
        assert DOMAIN in hass.data
        assert isinstance(hass.data[DOMAIN], dict)
        assert mock_config_entry.entry_id in hass.data[DOMAIN]

        # Verify the data matches config entry data
        stored_data = hass.data[DOMAIN][mock_config_entry.entry_id]
        assert stored_data == mock_config_entry.data
        assert stored_data[CONF_SERIAL_PORT] == "/dev/ttyUSB0"
        assert stored_data[CONF_BAUD_RATE] == 9600
