"""Test Home Assistant Cast."""

from unittest.mock import patch

import pytest

from homeassistant.components.cast import DOMAIN, home_assistant_cast
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry, async_mock_signal


@pytest.mark.usefixtures("mock_zeroconf")
async def test_service_show_view(hass: HomeAssistant) -> None:
    """Test showing a view."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await home_assistant_cast.async_setup_ha_cast(hass, entry)
    calls = async_mock_signal(hass, home_assistant_cast.SIGNAL_HASS_CAST_SHOW_VIEW)

    # No valid URL
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "cast",
            "show_lovelace_view",
            {"entity_id": "media_player.kitchen", "view_path": "mock_path"},
            blocking=True,
        )

    # Set valid URL
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    await hass.services.async_call(
        "cast",
        "show_lovelace_view",
        {"entity_id": "media_player.kitchen", "view_path": "mock_path"},
        blocking=True,
    )

    assert len(calls) == 1
    controller_data, entity_id, view_path, url_path = calls[0]
    assert controller_data["hass_url"] == "https://example.com"
    assert controller_data["client_id"] is None
    # Verify user did not accidentally submit their dev app id
    assert "supporting_app_id" not in controller_data
    assert entity_id == "media_player.kitchen"
    assert view_path == "mock_path"
    assert url_path is None


@pytest.mark.usefixtures("mock_zeroconf")
async def test_service_show_view_dashboard(hass: HomeAssistant) -> None:
    """Test casting a specific dashboard."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await home_assistant_cast.async_setup_ha_cast(hass, entry)
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
    _controller_data, entity_id, view_path, url_path = calls[0]
    assert entity_id == "media_player.kitchen"
    assert view_path == "mock_path"
    assert url_path == "mock-dashboard"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_use_cloud_url(hass: HomeAssistant) -> None:
    """Test that we fall back to cloud url."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    hass.config.components.add("cloud")

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await home_assistant_cast.async_setup_ha_cast(hass, entry)
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
    controller_data = calls[0][0]
    assert controller_data["hass_url"] == "https://something.nabu.casa"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_remove_entry(hass: HomeAssistant) -> None:
    """Test removing config entry removes user."""
    entry = MockConfigEntry(
        data={},
        domain="cast",
        title="Google Cast",
    )

    entry.add_to_hass(hass)

    with (
        patch("pychromecast.discovery.discover_chromecasts", return_value=(True, None)),
        patch("pychromecast.discovery.stop_discovery"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert "cast" in hass.config.components

    user_id = entry.data.get("user_id")
    assert await hass.auth.async_get_user(user_id)

    assert await hass.config_entries.async_remove(entry.entry_id)
    assert not await hass.auth.async_get_user(user_id)
