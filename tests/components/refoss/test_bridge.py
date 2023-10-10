"""Tests for refoss component."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.refoss.const import COORDINATORS, DOMAIN
from homeassistant.core import HomeAssistant

from .common import FakeDiscovery, async_setup_refoss, build_base_device_mock


async def test_discovery_after_setup(hass: HomeAssistant) -> None:
    """Test refoss device set up."""
    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=FakeDiscovery(),
    ), patch(
        "homeassistant.components.refoss.bridge.async_build_base_device",
        return_value=AsyncMock(),
    ) as mock_device:
        mock_device.return_value = build_base_device_mock(
            name="device-1", ip="1.1.1.1", mac="aabbcc112233"
        )

        await async_setup_refoss(hass)
        await hass.async_block_till_done()

        device_infos = [x.device for x in hass.data[DOMAIN][COORDINATORS]]
        assert device_infos[0].inner_ip == "1.1.1.1"
