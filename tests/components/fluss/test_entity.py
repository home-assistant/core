"""Test Script for Fluss Entity."""

import logging
from unittest.mock import AsyncMock, Mock, patch

from fluss_api import FlussApiClientCommunicationError
import pytest

from homeassistant.components.fluss.button import FlussButton
from homeassistant.components.fluss.const import DOMAIN
from homeassistant.components.fluss.entity import FlussEntity
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription

CONF_ADDRESS = "address"
CONF_API_KEY = "api_key"

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_entity_description() -> EntityDescription:
    """Return a mock entity description."""
    return EntityDescription(key="mock_key")


@pytest.fixture
def mock_entry() -> ConfigEntry:
    """Return a mock config entry."""
    entry = Mock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.data = {"api_key": "mock_api_key", "address": "mock_address"}
    entry.domain = DOMAIN
    entry.update_listeners = []
    entry.state = ConfigEntryState.LOADED
    return entry


@pytest.fixture
def mock_config_entries() -> Mock:
    """Return a mock ConfigEntries."""
    config_entries = Mock()
    config_entries.async_get_entry = Mock(return_value=None)
    config_entries.async_update_entry = AsyncMock()
    config_entries.async_entries = Mock(return_value=[])
    return config_entries


@pytest.fixture
def mock_fluss_button() -> Mock:
    """Return a mock FlussButton."""
    button = Mock(spec=FlussButton)
    button.unique_id = "mock_unique_id"
    button.async_update = AsyncMock()
    return button


@pytest.mark.asyncio
async def test_fluss_entity_initialization(
    hass: HomeAssistant,
    mock_fluss_button: Mock,
    mock_entry: ConfigEntry,
    mock_entity_description: EntityDescription,
    mock_config_entries: Mock,
) -> None:
    """Test FlussEntity initialization and attribute setup."""
    hass.config_entries = mock_config_entries

    entity = FlussEntity(
        hass=hass,
        device=mock_fluss_button,
        entry=mock_entry,
        entity_description=mock_entity_description,
    )
    entity._attr_unique_id = (
        f"{mock_fluss_button.unique_id}_{mock_entity_description.key}"
    )

    expected_unique_id = f"{mock_fluss_button.unique_id}_{mock_entity_description.key}"
    assert entity.unique_id == expected_unique_id


@pytest.mark.asyncio
async def test_fluss_entity_update_entry_data(
    hass: HomeAssistant,
    mock_fluss_button: Mock,
    mock_entry: ConfigEntry,
    mock_entity_description: EntityDescription,
    mock_config_entries: Mock,
) -> None:
    """Test FlussEntity updates entry data correctly."""
    mock_entry.data = {CONF_ADDRESS: "original_unique_id"}
    hass.config_entries = mock_config_entries

    mock_fluss_button.unique_id = "new_unique_id"

    with patch.object(hass.config_entries, "async_update_entry") as mock_update_entry:
        entity = FlussEntity(
            hass=hass,
            device=mock_fluss_button,
            entry=mock_entry,
            entity_description=mock_entity_description,
        )

        entity._update_entry_data()

        mock_update_entry.assert_called_once_with(
            mock_entry, data={"address": "new_unique_id"}
        )


@pytest.mark.asyncio
async def test_fluss_entity_no_update_needed(
    hass: HomeAssistant,
    mock_fluss_button: Mock,
    mock_entity_description: EntityDescription,
    mock_config_entries: Mock,
) -> None:
    """Test FlussEntity when no update to address is needed."""
    mock_entry = Mock(spec=ConfigEntry)
    mock_entry.entry_id = "test_entry"
    mock_entry.data = {CONF_ADDRESS: "mock_unique_id"}
    hass.config_entries = mock_config_entries

    mock_fluss_button.unique_id = "mock_unique_id"

    with patch.object(hass.config_entries, "async_update_entry") as mock_update_entry:
        entity = FlussEntity(
            hass=hass,
            device=mock_fluss_button,
            entry=mock_entry,
            entity_description=mock_entity_description,
        )
        entity._update_entry_data()
        mock_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_fluss_entity_async_update(
    hass: HomeAssistant,
    mock_fluss_button: Mock,
    mock_entry: ConfigEntry,
    mock_entity_description: EntityDescription,
    mock_config_entries: Mock,
) -> None:
    """Test FlussEntity async_update method."""
    hass.config_entries = mock_config_entries

    # Initialize the entity
    entity = FlussEntity(
        hass=hass,
        device=mock_fluss_button,
        entry=mock_entry,
        entity_description=mock_entity_description,
    )

    # Mock the async_update method of the device
    mock_fluss_button.async_update = AsyncMock()

    # Call the async_update method of the entity
    await entity.async_update()

    # Assert that the async_update method of the device was called
    mock_fluss_button.async_update.assert_called_once()


@pytest.mark.asyncio
async def test_fluss_entity_async_update_error(
    hass: HomeAssistant,
    mock_fluss_button: Mock,
    mock_entry: ConfigEntry,
    mock_entity_description: EntityDescription,
    mock_config_entries: Mock,
) -> None:
    """Test FlussEntity async_update method with communication error."""
    hass.config_entries = mock_config_entries

    # Initialize the entity
    entity = FlussEntity(
        hass=hass,
        device=mock_fluss_button,
        entry=mock_entry,
        entity_description=mock_entity_description,
    )

    # Simulate a communication error during async_update
    mock_fluss_button.async_update.side_effect = FlussApiClientCommunicationError()

    # Patch the logger to catch the error log
    with patch("homeassistant.components.fluss.entity._LOGGER.error") as mock_logger:
        await entity.async_update()
        mock_logger.assert_called_once_with(
            "Failed to update device: %s", mock_fluss_button
        )
