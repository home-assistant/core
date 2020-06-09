"""Test Home Assistant Cast."""
from homeassistant.components.cast import home_assistant_cast
from homeassistant.config import async_process_ha_core_config

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_mock_signal


async def test_service_show_view(hass):
    """Test we don't set app id in prod."""
    await async_process_ha_core_config(
        hass, {"external_url": "https://example.com"},
    )
    await home_assistant_cast.async_setup_ha_cast(hass, MockConfigEntry())
    calls = async_mock_signal(hass, home_assistant_cast.SIGNAL_HASS_CAST_SHOW_VIEW)

    await hass.services.async_call(
        "cast",
        "show_lovelace_view",
        {"entity_id": "media_player.kitchen", "view_path": "mock_path"},
        blocking=True,
    )

    assert len(calls) == 1
    controller, entity_id, view_path, url_path = calls[0]
    assert controller.hass_url == "https://example.com"
    assert controller.client_id is None
    # Verify user did not accidentally submit their dev app id
    assert controller.supporting_app_id == "B12CE3CA"
    assert entity_id == "media_player.kitchen"
    assert view_path == "mock_path"
    assert url_path is None


async def test_service_show_view_dashboard(hass):
    """Test casting a specific dashboard."""
    await async_process_ha_core_config(
        hass, {"external_url": "https://example.com"},
    )
    await home_assistant_cast.async_setup_ha_cast(hass, MockConfigEntry())
    calls = async_mock_signal(hass, home_assistant_cast.SIGNAL_HASS_CAST_SHOW_VIEW)

    await hass.services.async_call(
        "cast",
        "show_lovelace_view",
        {
            "entity_id": "media_player.kitchen",
            "view_path": "mock_path",
            "dashboard_path": "mock-dashboard",
        },
        blocking=True,
    )

    assert len(calls) == 1
    _controller, entity_id, view_path, url_path = calls[0]
    assert entity_id == "media_player.kitchen"
    assert view_path == "mock_path"
    assert url_path == "mock-dashboard"


async def test_use_cloud_url(hass):
    """Test that we fall back to cloud url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )
    hass.config.components.add("cloud")

    await home_assistant_cast.async_setup_ha_cast(hass, MockConfigEntry())
    calls = async_mock_signal(hass, home_assistant_cast.SIGNAL_HASS_CAST_SHOW_VIEW)

    with patch(
        "homeassistant.components.cloud.async_remote_ui_url",
        return_value="https://something.nabu.casa",
    ):
        await hass.services.async_call(
            "cast",
            "show_lovelace_view",
            {"entity_id": "media_player.kitchen", "view_path": "mock_path"},
            blocking=True,
        )

    assert len(calls) == 1
    controller = calls[0][0]
    assert controller.hass_url == "https://something.nabu.casa"
