"""Test services for the Snoo integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from python_snoo.containers import DiaperTypes

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import async_init_integration


async def test_log_diaper_change_service(
    hass: HomeAssistant, bypass_api: AsyncMock
) -> None:
    """Test the log_diaper_change service with all parameters."""
    await async_init_integration(hass)

    assert hass.services.has_service("snoo", "log_diaper_change")

    device_registry = dr.async_get(hass)
    baby_device = None

    for device in device_registry.devices.values():
        if device.model == "Baby":
            baby_device = device
            break

    assert baby_device is not None, (
        "Baby device should be created during integration setup"
    )

    with patch("python_snoo.baby.Baby.log_diaper_change") as mock_log_diaper_change:
        mock_log_diaper_change.return_value = MagicMock()

        await hass.services.async_call(
            "snoo",
            "log_diaper_change",
            {
                "baby_device_id": baby_device.id,
                "diaper_types": ["wet", "dirty"],
                "note": "Test note",
                "start_time": "2024-01-15T10:30:00",
            },
        )

        # Verify the service call was made with all parameters
        mock_log_diaper_change.assert_called_once()
        call_args = mock_log_diaper_change.call_args
        assert call_args[0][0] == [DiaperTypes.WET, DiaperTypes.DIRTY]
        assert call_args[1]["note"] == "Test note"
        assert call_args[1]["start_time"] is not None
