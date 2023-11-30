"""Test the FastdotcomDataUpdateCoordindator."""
from unittest.mock import patch

from homeassistant.components.fastdotcom.coordinator import (
    FastdotcomDataUpdateCoordindator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_fastdotcom_data_update_coordinator(hass: HomeAssistant) -> None:
    """Test the FastdotcomDataUpdateCoordindator."""
    coordinator = FastdotcomDataUpdateCoordindator(hass)

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com",
        return_value={"download": "50"},
    ):
        await coordinator.async_refresh()
        assert coordinator.data == {"download": "50"}

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com",
        side_effect=Exception("Test error"),
    ):
        await coordinator.async_refresh()
        assert coordinator.data == {"download": "50"}
        assert isinstance(coordinator.last_exception, UpdateFailed)
