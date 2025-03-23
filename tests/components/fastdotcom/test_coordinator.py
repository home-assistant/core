"""Test the FastdotcomDataUpdateCoordindator."""

from unittest.mock import patch

import pytest

from homeassistant.components.fastdotcom.coordinator import (
    FastdotcomDataUpdateCoordinator,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

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
        "ping_loaded": 20.5,
        "ping_unloaded": 15.2,
    }

    # Patch the fast_com2 function (used by the coordinator) to return fake_data.
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com2",
        return_value=fake_data,
    ):
        coordinator = FastdotcomDataUpdateCoordinator(hass, dummy_config_entry)
        await coordinator.async_refresh()
        assert coordinator.data == fake_data


async def test_coordinator_failure(hass, dummy_config_entry):
    """Test that the coordinator raises an UpdateFailed error when fast_com2 fails."""
    # Patch fast_com2 to raise an exception.
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com2",
        side_effect=Exception("Test error"),
    ):
        coordinator = FastdotcomDataUpdateCoordinator(hass, dummy_config_entry)
        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator.async_refresh()
        assert "Error communicating with Fast.com" in str(excinfo.value)
