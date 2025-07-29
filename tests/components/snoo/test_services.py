"""Test services for the Snoo integration."""

from unittest.mock import AsyncMock, patch

import pytest
from python_snoo.containers import DiaperTypes

from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_log_diaper_change_service(
    hass: HomeAssistant, bypass_api: AsyncMock
) -> None:
    """Test the log_diaper_change service."""
    await async_init_integration(hass)

    assert hass.services.has_service("snoo", "log_diaper_change")

    await hass.services.async_call(
        "snoo",
        "log_diaper_change",
        {"diaper_types": ["Wet"], "baby_id": "35235211235dfasdf32523"},
    )

    await hass.async_block_till_done()


async def test_log_diaper_change_with_all_parameters(
    hass: HomeAssistant, bypass_api: AsyncMock
) -> None:
    """Test service call with all optional parameters."""
    await async_init_integration(hass)

    # Mock successful API call
    with patch("homeassistant.components.snoo.services.Baby") as mock_baby:
        mock_baby.return_value.log_diaper_change = AsyncMock()

        await hass.services.async_call(
            "snoo",
            "log_diaper_change",
            {
                "diaper_types": ["Wet", "Dirty"],
                "baby_id": "35235211235dfasdf32523",
                "note": "Test note",
                "start_time": "2024-01-15T10:30:00",
            },
        )

        call_args = mock_baby.return_value.log_diaper_change.call_args
        assert call_args is not None
        assert call_args[0][0] == [
            # Should match enum values, which are all uppercase
            DiaperTypes["WET"],
            DiaperTypes["DIRTY"],
        ]  # diaper_types
        assert call_args[1]["note"] == "Test note"
        assert call_args[1]["start_time"] is not None


async def test_log_diaper_change_no_config_entries(
    hass: HomeAssistant, bypass_api: AsyncMock
) -> None:
    """Test service call when no config entries exist."""
    # Don't initialize the integration, so no config entries exist
    # The service won't be registered, so we expect a ServiceNotFound error

    with pytest.raises(Exception, match="service_not_found"):
        await hass.services.async_call(
            "snoo",
            "log_diaper_change",
            {"diaper_types": ["Wet"], "baby_id": "35235211235dfasdf32523"},
        )
