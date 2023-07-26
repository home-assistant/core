"""Test OTBR Utility functions."""

from homeassistant.components import otbr
from homeassistant.core import HomeAssistant

OTBR_MULTIPAN_URL = "http://core-silabs-multiprotocol:8081"
OTBR_NON_MULTIPAN_URL = "/dev/ttyAMA1"


async def test_get_allowed_channel(
    hass: HomeAssistant, multiprotocol_addon_manager_mock
) -> None:
    """Test get_allowed_channel."""

    # OTBR multipan + No configured channel -> no restriction
    multiprotocol_addon_manager_mock.async_get_channel.return_value = None
    assert await otbr.util.get_allowed_channel(hass, OTBR_MULTIPAN_URL) is None

    # OTBR multipan + multipan using channel 15 -> 15
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 15
    assert await otbr.util.get_allowed_channel(hass, OTBR_MULTIPAN_URL) == 15

    # OTBR no multipan + multipan using channel 15 -> no restriction
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 15
    assert await otbr.util.get_allowed_channel(hass, OTBR_NON_MULTIPAN_URL) is None
