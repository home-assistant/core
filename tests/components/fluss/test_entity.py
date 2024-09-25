"""Test Script for Fluss Entity."""

import logging
from unittest.mock import AsyncMock, Mock, patch

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
async def mock_entity_description() -> EntityDescription:
    """Return a mock entity description."""
    description = AsyncMock(spec=EntityDescription)
    description.key = "mock_key"
    return description


@pytest.fixture
async def mock_entry() -> ConfigEntry:
    """Return a mock config entry."""
    entry = AsyncMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.data = {"api_key": "mock_api_key", "address": "mock_address"}
    entry.domain = DOMAIN
    entry.update_listeners = []
    entry.state = ConfigEntryState.LOADED  # Ensure entry state is properly set
    return entry


@pytest.fixture
async def mock_config_entries() -> Mock:
    """Return a mock ConfigEntries."""
    config_entries = Mock()
    config_entries.async_get_entry = Mock(return_value=None)
    config_entries.async_update_entry = AsyncMock()
    config_entries.async_entries = Mock(return_value=[])
    return config_entries


@pytest.fixture
async def mock_fluss_button() -> Mock:
    """Return a mock FlussButton."""
    button = Mock(spec=FlussButton)
    button.unique_id = "mock_unique_id"
    button.state = "mock_state"
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

    expected_unique_id = (
        f"{mock_entry.data[CONF_ADDRESS]}_{mock_entity_description.key}"
    )

    assert entity.hass == hass
    assert entity.device == mock_fluss_button
    assert entity.entry == mock_entry
    assert entity.entity_description == mock_entity_description
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
    hass.config_entries = mock_config_entries

    mock_fluss_button.unique_id = "new_unique_id"
    with patch.object(hass.config_entries, "async_update_entry") as mock_update_entry:
        entity = FlussEntity(
            hass=hass,
            device=mock_fluss_button,
            entry=mock_entry,
            entity_description=mock_entity_description,
        )
        entity.async_write_ha_state = AsyncMock()  # Mock this if called
        entity._update_entry_data()

        mock_update_entry.assert_called_once_with(
            mock_entry,
            data={"api_key": "mock_api_key", "address": "new_unique_id"},
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

    with patch.object(hass.config_entries, "async_update_entry") as mock_update_entry:
        entity = FlussEntity(
            hass=hass,
            device=mock_fluss_button,
            entry=mock_entry,
            entity_description=mock_entity_description,
        )
        entity.async_write_ha_state = AsyncMock()  # Mock this if called
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


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item):
    """Pytest hook to add detailed logging for test results.

    This function is used to capture and log additional information
    during test execution, such as exceptions.
    """
    outcome = yield
    rep = outcome.get_result()
    if rep.failed:
        # Capture exception details
        if hasattr(rep.longrepr, "sections"):
            for section in rep.longrepr.sections:
                if section[0] == "Captured exception":
                    logger.error(section[1])
