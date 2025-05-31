"""Test Briiv integration setup."""

from unittest.mock import AsyncMock, patch

from pybriiv import BriivError

from homeassistant.components.briiv.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of entry."""
    # Create a mock entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.100",
            "port": 3334,
            "serial_number": "TEST123",
        },
        title="Test Briiv",
        unique_id="TEST123",
    )

    # Mock the BriivAPI class
    mock_api = AsyncMock()
    with patch("pybriiv.BriivAPI", return_value=mock_api):
        # Add entry to hass
        entry.add_to_hass(hass)

        # Setup the entry
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify API was initialized and start_listening was called
        mock_api.start_listening.assert_called_once()

        # Check entry is set up correctly
        assert entry.state is ConfigEntryState.LOADED

        # Check that runtime_data is properly set
        assert hasattr(entry, "runtime_data")
        assert entry.runtime_data.api == mock_api


async def test_setup_entry_failure(hass: HomeAssistant) -> None:
    """Test failed setup of entry."""
    # Create a mock entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.100",
            "port": 3334,
            "serial_number": "TEST123",
        },
        title="Test Briiv",
        unique_id="TEST123",
    )

    # Mock the BriivAPI class to raise an exception
    mock_api = AsyncMock()
    mock_api.start_listening.side_effect = BriivError("Failed to connect")
    with patch("pybriiv.BriivAPI", return_value=mock_api):
        # Add entry to hass
        entry.add_to_hass(hass)

        # Setup should fail
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify API was initialized but entry setup failed
        mock_api.start_listening.assert_called_once()
        mock_api.stop_listening.assert_called_once()

        # Check entry is in setup retry state
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading an entry."""
    # Create a mock entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.100",
            "port": 3334,
            "serial_number": "TEST123",
        },
        title="Test Briiv",
        unique_id="TEST123",
    )

    # Mock the BriivAPI class
    mock_api = AsyncMock()
    with patch("pybriiv.BriivAPI", return_value=mock_api):
        # Add entry to hass and set it up
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Now unload the entry
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify stop_listening was called
        mock_api.stop_listening.assert_called_once()

        # Check entry is unloaded
        assert entry.state is ConfigEntryState.NOT_LOADED

        # Entry should no longer have runtime_data after unload
        assert not hasattr(entry, "runtime_data") or entry.runtime_data is None


class MockConfigEntry:
    """Mock config entry for testing."""

    def __init__(self, domain, data, title, unique_id) -> None:
        """Initialize mock config entry."""
        self.domain = domain
        self.data = data
        self.title = title
        self.unique_id = unique_id
        self.entry_id = f"mock_{unique_id}"
        self.state = None
        self._hass = None
        self.runtime_data = None

    def add_to_hass(self, hass: HomeAssistant) -> None:
        """Add this entry to hass."""
        self._hass = hass
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
