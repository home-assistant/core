"""Test Home Assistant Cast."""
from unittest.mock import Mock
from homeassistant.components.cast import home_assistant_cast

from tests.common import MockConfigEntry, async_mock_signal


async def test_service_show_view(hass):
    """Test we don't set app id in prod."""
    hass.config.api = Mock(base_url="http://example.com")
    await home_assistant_cast.async_setup_ha_cast(hass, MockConfigEntry())
    calls = async_mock_signal(hass, home_assistant_cast.SIGNAL_HASS_CAST_SHOW_VIEW)

    await hass.services.async_call(
        "cast",
        "show_lovelace_view",
        {"entity_id": "media_player.kitchen", "view_path": "mock_path"},
        blocking=True,
    )

    assert len(calls) == 1
    controller, entity_id, view_path = calls[0]
    assert controller.hass_url == "http://example.com"
    assert controller.client_id is None
    # Verify user did not accidentally submit their dev app id
    assert controller.supporting_app_id == "B12CE3CA"
    assert entity_id == "media_player.kitchen"
    assert view_path == "mock_path"
