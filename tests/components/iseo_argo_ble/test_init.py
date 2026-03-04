"""Test the ISEO Argo BLE integration setup and teardown."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.iseo_argo_ble.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

from . import MOCK_ADDRESS, MOCK_PRIV_SCALAR, MOCK_UUID_HEX
from .conftest import mock_config_entry, mock_derive_private_key, mock_iseo_client  # noqa: F401


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that a config entry is set up correctly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state.value == "loaded"


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that a config entry is unloaded cleanly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Mock the erase_user call for gateway unload
        mock_iseo_client.erase_user = AsyncMock(return_value=None)

        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state.value == "not_loaded"
