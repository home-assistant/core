"""Test OTBR Utility functions."""
from unittest.mock import Mock, patch

from homeassistant.components import otbr
from homeassistant.core import HomeAssistant

OTBR_MULTIPAN_URL = "http://core-silabs-multiprotocol:8081"
OTBR_NON_MULTIPAN_URL = "/dev/ttyAMA1"


async def test_get_allowed_channel(hass: HomeAssistant) -> None:
    """Test get_allowed_channel."""

    zha_networksettings = Mock()
    zha_networksettings.network_info.channel = 15

    # OTBR multipan + No ZHA -> no restriction
    assert await otbr.util.get_allowed_channel(hass, OTBR_MULTIPAN_URL) is None

    # OTBR multipan + ZHA multipan empty settings -> no restriction
    with patch(
        "homeassistant.components.otbr.util.zha_api.async_get_radio_path",
        return_value="socket://core-silabs-multiprotocol:9999",
    ), patch(
        "homeassistant.components.otbr.util.zha_api.async_get_network_settings",
        return_value=None,
    ):
        assert await otbr.util.get_allowed_channel(hass, OTBR_MULTIPAN_URL) is None

    # OTBR multipan + ZHA not multipan using channel 15 -> no restriction
    with patch(
        "homeassistant.components.otbr.util.zha_api.async_get_radio_path",
        return_value="/dev/ttyAMA1",
    ), patch(
        "homeassistant.components.otbr.util.zha_api.async_get_network_settings",
        return_value=zha_networksettings,
    ):
        assert await otbr.util.get_allowed_channel(hass, OTBR_MULTIPAN_URL) is None

    # OTBR multipan + ZHA multipan using channel 15 -> 15
    with patch(
        "homeassistant.components.otbr.util.zha_api.async_get_radio_path",
        return_value="socket://core-silabs-multiprotocol:9999",
    ), patch(
        "homeassistant.components.otbr.util.zha_api.async_get_network_settings",
        return_value=zha_networksettings,
    ):
        assert await otbr.util.get_allowed_channel(hass, OTBR_MULTIPAN_URL) == 15

    # OTBR not multipan + ZHA multipan using channel 15 -> no restriction
    with patch(
        "homeassistant.components.otbr.util.zha_api.async_get_radio_path",
        return_value="socket://core-silabs-multiprotocol:9999",
    ), patch(
        "homeassistant.components.otbr.util.zha_api.async_get_network_settings",
        return_value=zha_networksettings,
    ):
        assert await otbr.util.get_allowed_channel(hass, OTBR_NON_MULTIPAN_URL) is None
