"""Test the FastdotcomDataUpdateCoordindator."""

from unittest.mock import patch

import pytest

from homeassistant.components.fastdotcom.coordinator import (
    FastdotcomDataUpdateCoordinator,
)

from tests.common import MockConfigEntry


@pytest.fixture
def dummy_config_entry():
    """Return a dummy config entry for Fast.com."""
    return MockConfigEntry(domain="fastdotcom", data={}, entry_id="test_entry")


async def test_coordinator_success(hass, dummy_config_entry):
    """Test that the coordinator successfully fetches data from Fast.com."""
    fake_data = {
        "download_speed": 100.0,
        "upload_speed": 50.0,
        "unloaded_ping": 15.2,
        "loaded_ping": 20.2,
    }

    # Patch the fast_com function (used by the coordinator) to return fake_data.
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com",
        return_value=fake_data,
    ):
        coordinator = FastdotcomDataUpdateCoordinator(hass, dummy_config_entry)
        await coordinator.async_refresh()
        # Wait for background tasks to complete
        await hass.async_block_till_done()
        assert coordinator.data == fake_data


async def test_coordinator_failure(hass, dummy_config_entry):
    """Test that the coordinator handles failure by setting last_update_success to False and clearing data."""
    # Patch fast_com to raise an exception.
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com",
        side_effect=Exception("Test error"),
    ):
        coordinator = FastdotcomDataUpdateCoordinator(hass, dummy_config_entry)
        await coordinator.async_refresh()
        # Wait for background tasks to complete
        await hass.async_block_till_done()
        assert coordinator.last_update_success is False
        assert coordinator.data == {} or coordinator.data is None
