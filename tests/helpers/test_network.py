"""Test network helper."""
from homeassistant.components import cloud
from homeassistant.helpers import network

from tests.async_mock import Mock, patch


async def test_get_external_url(hass):
    """Test get_external_url."""
    hass.config.api = Mock(base_url="http://192.168.1.100:8123")

    assert network.async_get_external_url(hass) is None

    hass.config.api = Mock(base_url="http://example.duckdns.org:8123")

    assert network.async_get_external_url(hass) == "http://example.duckdns.org:8123"

    hass.config.components.add("cloud")

    assert network.async_get_external_url(hass) == "http://example.duckdns.org:8123"

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        side_effect=cloud.CloudNotAvailable,
    ):
        assert network.async_get_external_url(hass) == "http://example.duckdns.org:8123"

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        return_value="https://example.nabu.casa",
    ):
        assert network.async_get_external_url(hass) == "https://example.nabu.casa"
