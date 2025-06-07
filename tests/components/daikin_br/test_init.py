"""Tests for initializing the Daikin Smart AC (daikin_br) integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.daikin_br import (
    PLATFORMS,
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.daikin_br.const import DOMAIN
from homeassistant.components.daikin_br.coordinator import (
    DaikinDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import MockConfigEntry


# pylint: disable=redefined-outer-name, too-few-public-methods
# pylint: disable=protected-access
# Define a dummy config entry to simulate a Home Assistant ConfigEntry.
class DummyConfigEntry:
    """Dummy config entry for testing purposes."""

    def __init__(self, data: dict) -> None:
        """Initialize dummy config entries."""
        self.entry_id = "dummy_entry"
        self.data = data
        self.runtime_data = None


# Dummy coordinator to simulate runtime_data.
class DummyCoordinator:
    """Dummy coordinator to simulate runtime_data."""

    def __init__(self, data) -> None:
        """Initialize dummy coordinator."""
        self.data = data  # For example, a dict of device identifiers


# Dummy device entry that mimics a Home Assistant DeviceEntry.
class DummyDeviceEntry:
    """Dummy device entry that mimics a Home Assistant DeviceEntry."""

    def __init__(self, identifiers) -> None:
        """Initialize dummy device entry."""
        # identifiers should be an iterable (e.g. a set) of tuples.
        self.identifiers = identifiers


@pytest.fixture
def dummy_config_entry():
    """Return a function that creates a DummyConfigEntry from given data."""

    def _create(data: dict) -> DummyConfigEntry:
        return DummyConfigEntry(data)

    return _create


# Parametrized test: for each missing key, the setup should fail.
@pytest.mark.parametrize("missing_key", [CONF_API_KEY, "host", "device_apn"])
@pytest.mark.asyncio
async def test_setup_entry_missing_required_data(
    hass: HomeAssistant, dummy_config_entry, missing_key
) -> None:
    """Test that async_setup_entry returns False and logs an error when required.

    Configuration data is missing.
    """
    # Base valid data.
    data = {
        CONF_API_KEY: "VALID_KEY",
        "host": "192.168.1.100",
        "device_apn": "TEST_APN",
        "device_name": "TEST DEVICE",
    }
    # Remove one required key.
    data.pop(missing_key, None)

    entry = dummy_config_entry(data)
    # caplog.set_level("ERROR")
    result = await async_setup_entry(hass, entry)
    assert result is False
    # assert "Missing required configuration data" in caplog.text


@pytest.mark.asyncio
async def test_setup_entry_update_failed(
    hass: HomeAssistant, dummy_config_entry
) -> None:
    """Test that async_setup_entry raises ConfigEntryNotReady.

    When the coordinator's first refresh raises UpdateFailed.
    """
    entry = dummy_config_entry(
        {
            "api_key": "VALID_KEY",
            "host": "192.168.1.100",
            "device_apn": "TEST_APN",
            "device_name": "TEST DEVICE",
        }
    )

    # Use a single `with` statement for multiple patches
    with (
        patch(
            "homeassistant.components.daikin_br.async_get_thing_info",
            new=AsyncMock(side_effect=UpdateFailed("Test update failed")),
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_setup_entry_unexpected_exception(
    hass: HomeAssistant, dummy_config_entry
) -> None:
    """Test that async_setup_entry raises ConfigEntryNotReady.

    When an unexpected exception occurs during coordinator update.
    """
    entry = dummy_config_entry(
        {
            CONF_API_KEY: "VALID_KEY",
            "host": "192.168.1.100",
            "device_apn": "TEST_APN",
            "device_name": "TEST DEVICE",
        }
    )

    # Use a single `with` statement for patching and exception assertion
    with (
        patch(
            "homeassistant.components.daikin_br.async_get_thing_info",
            new=AsyncMock(side_effect=Exception("Unexpected test error")),
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant, dummy_config_entry
) -> None:
    """Test async_setup_entry initializes the coordinator correctly.

    Performs a refresh, stores runtime_data, and forwards platform setup.
    """
    entry = dummy_config_entry(
        {
            "api_key": "VALID_KEY",
            "host": "192.168.1.100",
            "device_apn": "TEST_APN",
            "device_name": "TEST DEVICE",
        }
    )

    original_init = DataUpdateCoordinator.__init__

    # pylint: disable=duplicate-code
    def dummy_init(self, hass: HomeAssistant, logger, **kwargs) -> None:
        """Override __init__ to accept extra args without breaking HA."""
        self.hass = hass
        self.logger = logger
        self.config_entry = kwargs.get("config_entry")
        self.name = kwargs.get("name")
        self.update_interval = kwargs.get("update_interval")
        self.data = {}

    DataUpdateCoordinator.__init__ = dummy_init

    try:
        with (
            patch(
                "homeassistant.components.daikin_br.async_get_thing_info",
                new=AsyncMock(return_value={"port1": {"fw_ver": "1.0.0"}}),
            ) as mock_get_info,
            patch.object(
                DaikinDataUpdateCoordinator,
                "async_config_entry_first_refresh",
                new=AsyncMock(),
            ) as mock_refresh,
            patch.object(
                hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
            ) as mock_forward,
        ):
            result = await async_setup_entry(hass, entry)

    finally:
        # Restore the original __init__ method
        DataUpdateCoordinator.__init__ = original_init

    assert result is True
    assert entry.runtime_data is not None
    assert isinstance(entry.runtime_data, DaikinDataUpdateCoordinator)

    mock_get_info.assert_awaited_once()
    mock_refresh.assert_awaited_once()
    mock_forward.assert_awaited_once_with(entry, PLATFORMS)


@pytest.mark.asyncio
async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test that async_unload_entry unloads the config entry correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"key": "value"}, unique_id="test_entry"
    )
    entry.add_to_hass(hass)

    # Simulate that the entry is stored in hass.data.
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    result = await async_unload_entry(hass, entry)
    assert result is True

    # Verify that the entry is removed from hass.data.
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.asyncio
async def test_remove_config_entry_device_runtime_data_none() -> None:
    """Test that async_remove_config_entry_device returns True when runtime_data.

    Data is None.
    """
    data = {"dummy_key": "dummy_value"}
    entry = DummyConfigEntry(data)
    # Set runtime_data.data to None.
    entry.runtime_data = DummyCoordinator(data=None)

    # Create a dummy device entry with any identifier.
    device_entry = DummyDeviceEntry(identifiers={(DOMAIN, "TEST_APN")})

    # Since runtime_data.data is None (treated as empty).
    # The function should return True.
    result = await async_remove_config_entry_device(None, entry, device_entry)
    assert result is True
