"""Unit tests for router."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.asuswrt.router import AsusWrtRouter
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_get_rates_none_value(hass: HomeAssistant) -> None:
    """Test AsusWrtLegacyBridge._get_rates with None value."""
    with (
        patch(
            "homeassistant.components.asuswrt.router.AsusWrtBridge.get_bridge"
        ) as bridge,
        patch(
            "homeassistant.components.asuswrt.router.async_dispatcher_send"
        ) as mocked_dispatcher,
    ):
        bridge.return_value.async_get_connected_devices = AsyncMock(
            side_effect=ConnectionError("Unable to connect")
        )
        _router = AsusWrtRouter(hass, MockConfigEntry())
        assert not await _router.update_devices()
        mocked_dispatcher.assert_not_called()
