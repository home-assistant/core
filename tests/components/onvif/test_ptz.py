"""Test ONVIF PTZ capabilities."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.onvif.device import CONTINUOUS_MOVE, ONVIFDevice
from homeassistant.components.onvif.models import Capabilities
from homeassistant.core import HomeAssistant


async def test_continuous_move_calls_stop_when_duration_nonzero(
    hass: HomeAssistant,
) -> None:
    """Test PTZ ContinuousMove calls stop when duration is nonzero."""
    # Build a real ONVIFDevice without integration setup
    dev = ONVIFDevice.__new__(ONVIFDevice)  # bypass __init__
    dev.hass = hass
    dev.capabilities = Capabilities(imaging=True, ptz=True)

    # Mock the underlying ONVIFCamera object (`self.device`)
    dev.device = MagicMock()
    ptz_service = SimpleNamespace()
    ptz_service.create_type = MagicMock(side_effect=lambda name: SimpleNamespace())
    ptz_service.ContinuousMove = AsyncMock()
    ptz_service.Stop = AsyncMock()
    dev.device.create_ptz_service = AsyncMock(return_value=ptz_service)

    profile = SimpleNamespace(
        token="profile_token",
        ptz=SimpleNamespace(continuous=True),
    )

    with patch(
        "homeassistant.components.onvif.device.asyncio.sleep", new=AsyncMock()
    ) as mock_sleep:
        await dev.async_perform_ptz(
            profile=profile,
            distance=1,
            speed=1,
            move_mode=CONTINUOUS_MOVE,
            continuous_duration=2,
            preset=None,
            pan=0,
            tilt=0,
            zoom=None,
        )

    # Sleep should be called with 2
    mock_sleep.assert_awaited_once_with(2)

    # ContinuousMove should happen
    ptz_service.ContinuousMove.assert_awaited_once()

    # Stop should be called
    ptz_service.Stop.assert_awaited_once()


async def test_continuous_move_does_not_call_stop_when_duration_zero(
    hass: HomeAssistant,
) -> None:
    """Test PTZ ContinuousMove does not call stop when duration is zero."""
    # Create a real ONVIFDevice instance without running its __init__
    dev = ONVIFDevice.__new__(ONVIFDevice)
    dev.hass = hass
    dev.capabilities = Capabilities(imaging=True, ptz=True)

    # Mock the underlying ONVIFCamera object (self.device)
    dev.device = MagicMock()
    ptz_service = SimpleNamespace()
    ptz_service.create_type = MagicMock(side_effect=lambda name: SimpleNamespace())
    ptz_service.ContinuousMove = AsyncMock()
    ptz_service.Stop = AsyncMock()
    dev.device.create_ptz_service = AsyncMock(return_value=ptz_service)

    profile = SimpleNamespace(
        token="profile_token",
        ptz=SimpleNamespace(continuous=True),
    )

    with patch(
        "homeassistant.components.onvif.device.asyncio.sleep", new=AsyncMock()
    ) as mock_sleep:
        await dev.async_perform_ptz(
            profile=profile,
            distance=1,
            speed=1,
            move_mode=CONTINUOUS_MOVE,
            continuous_duration=0,  # ZERO duration
            preset=None,
            pan=0,
            tilt=0,
            zoom=None,
        )

    # Sleep should NOT be called
    mock_sleep.assert_not_awaited()

    # ContinuousMove should still happen
    ptz_service.ContinuousMove.assert_awaited_once()

    # Stop should NOT be called
    ptz_service.Stop.assert_not_called()
