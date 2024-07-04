"""Test setting up and unloading Russound RIO."""

from unittest.mock import patch

import pytest

from homeassistant.components.russound_rio import async_setup_entry, async_unload_entry
from homeassistant.components.russound_rio.const import DOMAIN, RUSSOUND_RIO_EXCEPTIONS
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

MOCK_CONFIG = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 9621,
}


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry, mock_russound, mock_asyncio_timeout
) -> None:
    """Test setting up the Russound RIO entry."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
    ) as mock_forward_entry_setups:
        assert await async_setup_entry(hass, mock_config_entry)

        # Ensure the Russound instance is stored in hass.data
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]

        # Verify the Russound instance was initialized correctly
        russ_instance = hass.data[DOMAIN][mock_config_entry.entry_id]
        assert russ_instance == mock_russound.return_value
        mock_russound.assert_called_once_with(
            hass.loop, MOCK_CONFIG[CONF_HOST], MOCK_CONFIG[CONF_PORT]
        )
        mock_russound.return_value.connect.assert_called_once()

        # Verify the forward setup of platforms
        mock_forward_entry_setups.assert_called_once_with(
            mock_config_entry, [Platform.MEDIA_PLAYER]
        )


@pytest.mark.asyncio
async def test_async_setup_entry_failure(
    hass: HomeAssistant, mock_config_entry, mock_russound
) -> None:
    """Test handling setup failure."""
    mock_russound.return_value.connect.side_effect = RUSSOUND_RIO_EXCEPTIONS[0](
        "Test Error"
    )

    with (
        pytest.raises(ConfigEntryError),
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry, mock_russound
) -> None:
    """Test unloading the Russound RIO entry."""
    # Set up the entry first
    with patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"):
        await async_setup_entry(hass, mock_config_entry)

    # Now test unloading it
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ) as mock_unload_platforms:
        unload_ok = await async_unload_entry(hass, mock_config_entry)
        assert unload_ok
        assert mock_config_entry.entry_id not in hass.data[DOMAIN]
        mock_russound.return_value.close.assert_called_once()
        mock_unload_platforms.assert_called_once_with(
            mock_config_entry, [Platform.MEDIA_PLAYER]
        )
