"""Test the Lovelace Cast platform."""
from time import time
from unittest.mock import patch

import pytest

from homeassistant.components.lovelace import cast as lovelace_cast
from homeassistant.config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture
async def mock_https_url(hass):
    """Mock valid URL."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )


@pytest.fixture
async def mock_yaml_dashboard(hass):
    """Mock the content of a YAML dashboard."""
    # Set up a YAML dashboard with 2 views.
    assert await async_setup_component(
        hass,
        "lovelace",
        {
            "lovelace": {
                "dashboards": {
                    "yaml-with-views": {
                        "title": "YAML Title",
                        "mode": "yaml",
                        "filename": "bla.yaml",
                    }
                }
            }
        },
    )

    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml",
        return_value={
            "title": "YAML Title",
            "views": [
                {
                    "title": "Hello",
                },
                {"path": "second-view"},
            ],
        },
    ), patch(
        "homeassistant.components.lovelace.dashboard.os.path.getmtime",
        return_value=time() + 10,
    ):
        yield


async def test_root_object(hass):
    """Test getting a root object."""
    assert (
        await lovelace_cast.async_get_media_browser_root_object(hass, "some-type") == []
    )

    root = await lovelace_cast.async_get_media_browser_root_object(
        hass, lovelace_cast.CAST_TYPE_CHROMECAST
    )
    assert len(root) == 1
    item = root[0]
    assert item.title == "Dashboards"
    assert item.media_class == lovelace_cast.MEDIA_CLASS_APP
    assert item.media_content_id == ""
    assert item.media_content_type == lovelace_cast.DOMAIN
    assert item.thumbnail == "https://brands.home-assistant.io/_/lovelace/logo.png"
    assert item.can_play is False
    assert item.can_expand is True


async def test_browse_media_error(hass):
    """Test browse media checks valid URL."""
    assert await async_setup_component(hass, "lovelace", {})

    with pytest.raises(HomeAssistantError):
        await lovelace_cast.async_browse_media(
            hass, "lovelace", "", lovelace_cast.CAST_TYPE_CHROMECAST
        )

    assert (
        await lovelace_cast.async_browse_media(
            hass, "not_lovelace", "", lovelace_cast.CAST_TYPE_CHROMECAST
        )
        is None
    )


async def test_browse_media(hass, mock_yaml_dashboard, mock_https_url):
    """Test browse media."""
    top_level_items = await lovelace_cast.async_browse_media(
        hass, "lovelace", "", lovelace_cast.CAST_TYPE_CHROMECAST
    )

    assert len(top_level_items.children) == 2

    child_1 = top_level_items.children[0]
    assert child_1.title == "Default"
    assert child_1.media_class == lovelace_cast.MEDIA_CLASS_APP
    assert child_1.media_content_id == lovelace_cast.DEFAULT_DASHBOARD
    assert child_1.media_content_type == lovelace_cast.DOMAIN
    assert child_1.thumbnail == "https://brands.home-assistant.io/_/lovelace/logo.png"
    assert child_1.can_play is True
    assert child_1.can_expand is False

    child_2 = top_level_items.children[1]
    assert child_2.title == "YAML Title"
    assert child_2.media_class == lovelace_cast.MEDIA_CLASS_APP
    assert child_2.media_content_id == "yaml-with-views"
    assert child_2.media_content_type == lovelace_cast.DOMAIN
    assert child_2.thumbnail == "https://brands.home-assistant.io/_/lovelace/logo.png"
    assert child_2.can_play is True
    assert child_2.can_expand is True

    child_2 = await lovelace_cast.async_browse_media(
        hass, "lovelace", child_2.media_content_id, lovelace_cast.CAST_TYPE_CHROMECAST
    )

    assert len(child_2.children) == 2

    grandchild_1 = child_2.children[0]
    assert grandchild_1.title == "Hello"
    assert grandchild_1.media_class == lovelace_cast.MEDIA_CLASS_APP
    assert grandchild_1.media_content_id == "yaml-with-views/0"
    assert grandchild_1.media_content_type == lovelace_cast.DOMAIN
    assert (
        grandchild_1.thumbnail == "https://brands.home-assistant.io/_/lovelace/logo.png"
    )
    assert grandchild_1.can_play is True
    assert grandchild_1.can_expand is False

    grandchild_2 = child_2.children[1]
    assert grandchild_2.title == "second-view"
    assert grandchild_2.media_class == lovelace_cast.MEDIA_CLASS_APP
    assert grandchild_2.media_content_id == "yaml-with-views/second-view"
    assert grandchild_2.media_content_type == lovelace_cast.DOMAIN
    assert (
        grandchild_2.thumbnail == "https://brands.home-assistant.io/_/lovelace/logo.png"
    )
    assert grandchild_2.can_play is True
    assert grandchild_2.can_expand is False

    with pytest.raises(HomeAssistantError):
        await lovelace_cast.async_browse_media(
            hass,
            "lovelace",
            "non-existing-dashboard",
            lovelace_cast.CAST_TYPE_CHROMECAST,
        )


async def test_play_media(hass, mock_yaml_dashboard):
    """Test playing media."""
    calls = async_mock_service(hass, "cast", "show_lovelace_view")

    await lovelace_cast.async_play_media(
        hass, "media_player.my_cast", None, "lovelace", lovelace_cast.DEFAULT_DASHBOARD
    )

    assert len(calls) == 1
    assert calls[0].data["entity_id"] == "media_player.my_cast"
    assert "dashboard_path" not in calls[0].data
    assert calls[0].data["view_path"] == "0"

    await lovelace_cast.async_play_media(
        hass, "media_player.my_cast", None, "lovelace", "yaml-with-views/second-view"
    )

    assert len(calls) == 2
    assert calls[1].data["entity_id"] == "media_player.my_cast"
    assert calls[1].data["dashboard_path"] == "yaml-with-views"
    assert calls[1].data["view_path"] == "second-view"
