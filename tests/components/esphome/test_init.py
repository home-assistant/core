"""ESPHome set up tests."""

from unittest.mock import AsyncMock

from aioesphomeapi import APIConnectionError
import pytest

from homeassistant.components.esphome import DOMAIN
from homeassistant.components.esphome.const import CONF_NOISE_PSK
from homeassistant.components.esphome.encryption_key_storage import (
    async_get_encryption_key_storage,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_client", "mock_zeroconf")
async def test_remove_entry(hass: HomeAssistant) -> None:
    """Test we can remove an entry without error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="mock-config-name",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_clears_dynamic_encryption_key(
    hass: HomeAssistant,
    mock_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that removing an entry clears the dynamic encryption key from device and storage."""
    # Store the encryption key to simulate it was dynamically generated
    storage = await async_get_encryption_key_storage(hass)
    await storage.async_store_key(
        mock_config_entry.unique_id, mock_config_entry.data[CONF_NOISE_PSK]
    )
    assert (
        await storage.async_get_key(mock_config_entry.unique_id)
        == mock_config_entry.data[CONF_NOISE_PSK]
    )

    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.connect.assert_called_once()
    mock_client.noise_encryption_set_key.assert_called_once_with(b"")
    mock_client.disconnect.assert_called_once()

    assert await storage.async_get_key(mock_config_entry.unique_id) is None


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_no_noise_psk(hass: HomeAssistant, mock_client) -> None:
    """Test that removing an entry without noise_psk does not attempt to clear encryption key."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            # No CONF_NOISE_PSK
        },
        unique_id="11:22:33:44:55:aa",
    )
    mock_config_entry.add_to_hass(hass)

    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.noise_encryption_set_key.assert_not_called()


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_user_provided_key(
    hass: HomeAssistant,
    mock_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that removing an entry with user-provided key does not clear it."""
    # Do not store the key in storage - simulates user-provided key
    storage = await async_get_encryption_key_storage(hass)
    assert await storage.async_get_key(mock_config_entry.unique_id) is None

    mock_client.noise_encryption_set_key = AsyncMock(return_value=True)

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.noise_encryption_set_key.assert_not_called()


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_device_rejects_key_removal(
    hass: HomeAssistant,
    mock_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that when device rejects key removal, key remains in storage."""
    # Store the encryption key to simulate it was dynamically generated
    storage = await async_get_encryption_key_storage(hass)
    await storage.async_store_key(
        mock_config_entry.unique_id, mock_config_entry.data[CONF_NOISE_PSK]
    )

    mock_client.noise_encryption_set_key = AsyncMock(return_value=False)

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.connect.assert_called_once()
    mock_client.noise_encryption_set_key.assert_called_once_with(b"")
    mock_client.disconnect.assert_called_once()

    assert (
        await storage.async_get_key(mock_config_entry.unique_id)
        == mock_config_entry.data[CONF_NOISE_PSK]
    )


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry_connection_error(
    hass: HomeAssistant,
    mock_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that connection error during key clearing does not remove key from storage."""
    # Store the encryption key to simulate it was dynamically generated
    storage = await async_get_encryption_key_storage(hass)
    await storage.async_store_key(
        mock_config_entry.unique_id, mock_config_entry.data[CONF_NOISE_PSK]
    )

    mock_client.connect = AsyncMock(side_effect=APIConnectionError("Connection failed"))

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.connect.assert_called_once()
    mock_client.disconnect.assert_called_once()

    assert (
        await storage.async_get_key(mock_config_entry.unique_id)
        == mock_config_entry.data[CONF_NOISE_PSK]
    )
