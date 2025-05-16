"""Tests for the Daikin BR coordinator."""

import datetime
from unittest.mock import MagicMock

import pytest

from homeassistant.components.daikin_br.coordinator import DaikinDataUpdateCoordinator
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


# pylint: disable=redefined-outer-name, too-few-public-methods
# pylint: disable=protected-access
# Dummy hass fixture for testing.
@pytest.fixture
def dummy_hass():
    """Create a dummy hass object for testing."""
    return MagicMock()


# Define a dummy config entry class that mimics a Home Assistant ConfigEntry.
class DummyConfigEntry:
    """dummy config entry class that mimics a Home Assistant ConfigEntry."""

    def __init__(self, data: dict) -> None:
        """Initilze the class with default values."""
        self.entry_id = "dummy_entry"
        self.data = data
        self.runtime_data = None


@pytest.fixture
def dummy_config_entry():
    """Create dummy data."""
    data = {
        CONF_API_KEY: "VALID_KEY",
        "device_apn": "TEST_APN",
        "host": "192.168.1.100",
        "device_name": "TEST DEVICE",
    }
    return DummyConfigEntry(data)


class DummyCoordinator:
    """Create dummy data coordinator."""

    def __init__(self) -> None:
        """Initialize data coordinator."""
        # Accept any parameters (including config_entry) without error.
        self.data = {}  # Dummy data attribute

    async def async_config_entry_first_refresh(self):
        """Simulate update failed."""
        raise UpdateFailed("Test update failed")


# Test case 1: Valid data returned by update_method.
@pytest.mark.asyncio
async def test_async_update_data_valid(dummy_hass, dummy_config_entry) -> None:
    """Test _async_update_data returns valid data when update_method returns a dict."""

    async def update_method():
        return {"port1": {"fw_ver": "1.0.0", "temperature": 22}}

    # Patch DataUpdateCoordinator.__init__ to accept extra keyword arguments
    original_init = DataUpdateCoordinator.__init__

    def dummy_init(self, hass: HomeAssistant, logger, **kwargs):
        # Simply store the provided arguments.
        self.hass = hass
        self.logger = logger
        self.config_entry = kwargs.get("config_entry")
        self.name = kwargs.get("name")
        self.update_interval = kwargs.get("update_interval")

    DataUpdateCoordinator.__init__ = dummy_init

    # Create a dummy config entry.
    entry = dummy_config_entry

    coordinator = DaikinDataUpdateCoordinator(
        dummy_hass,
        entry,
        device_apn="TEST_APN",
        update_method=update_method,
        update_interval=datetime.timedelta(seconds=10),
    )

    # Restore the original __init__ method.
    DataUpdateCoordinator.__init__ = original_init

    data = await coordinator._async_update_data()
    assert isinstance(data, dict)
    assert data == {"port1": {"fw_ver": "1.0.0", "temperature": 22}}


@pytest.mark.asyncio
async def test_async_update_data_invalid_type(dummy_hass, dummy_config_entry) -> None:
    """Test _async_update_data raises UpdateFailed.

    When update_method returns a non-dict.
    """

    async def update_method():
        return "invalid"  # not a dict

    # Patch DataUpdateCoordinator.__init__ to accept extra keyword arguments
    original_init = DataUpdateCoordinator.__init__

    def dummy_init(self, hass: HomeAssistant, logger, **kwargs):
        # Simply store the provided arguments.
        self.hass = hass
        self.logger = logger
        self.config_entry = kwargs.get("config_entry")
        self.name = kwargs.get("name")
        self.update_interval = kwargs.get("update_interval")

    DataUpdateCoordinator.__init__ = dummy_init

    # Create a dummy config entry.
    entry = dummy_config_entry

    coordinator = DaikinDataUpdateCoordinator(
        dummy_hass,
        entry,
        device_apn="TEST_APN",
        update_method=update_method,
        update_interval=datetime.timedelta(seconds=10),
    )
    # caplog.set_level(logging.DEBUG)

    # Restore the original __init__ method.
    DataUpdateCoordinator.__init__ = original_init

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    # Verify that the exception message
    # includes the device APN and a descriptive message.
    assert "The device TEST_APN is unavailable" in str(exc_info.value)
    # Optionally, verify that the expected debug message was logged.
    # assert "Unable to retrieve device status data for TEST_APN" in caplog.text


# pylint: disable=broad-exception-raised
@pytest.mark.asyncio
async def test_async_update_data_exception(dummy_hass, dummy_config_entry) -> None:
    """Test that _async_update_data raises UpdateFailed.

    Also verify that the error is logged.
    """

    async def update_method():
        raise Exception("Test exception")  # noqa: TRY002

    # Patch DataUpdateCoordinator.__init__ to accept extra keyword arguments
    original_init = DataUpdateCoordinator.__init__

    def dummy_init(self, hass: HomeAssistant, logger, **kwargs):
        # Simply store the provided arguments.
        self.hass = hass
        self.logger = logger
        self.config_entry = kwargs.get("config_entry")
        self.name = kwargs.get("name")
        self.update_interval = kwargs.get("update_interval")

    DataUpdateCoordinator.__init__ = dummy_init

    entry = dummy_config_entry
    # caplog.set_level(logging.DEBUG)

    coordinator = DaikinDataUpdateCoordinator(
        dummy_hass,
        entry,
        device_apn="TEST_APN",
        update_method=update_method,
        update_interval=datetime.timedelta(seconds=10),
    )

    # Restore the original __init__ method.
    DataUpdateCoordinator.__init__ = original_init

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    # Verify that the UpdateFailed message includes the expected text.
    assert "The device TEST_APN is unavailable: Test exception" in str(exc_info.value)
    # Check that a debug message is logged indicating an error.
    # assert "Error fetching data for TEST_APN:" in caplog.text
