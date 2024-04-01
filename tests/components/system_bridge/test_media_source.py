"""Test the System Bridge integration."""

from unittest.mock import MagicMock

from homeassistant.components.media_source import URI_SCHEME, async_browse_media
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FIXTURE_UUID, setup_integration

from tests.common import MockConfigEntry


async def test_async_browse_media(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: MagicMock,
) -> None:
    """Test async_browse_media."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.LOADED

    # Get device from device registry
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, FIXTURE_UUID)},
    )
    assert device is not None

    # # Get media source
    # media_source = await async_get_media_source(hass)

    # # Test browse media
    # browse_media = await media_source.async_browse_media(None)

    media = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}",
    )

    assert media.as_dict() == {
        "title": "System Bridge",
        "media_class": "directory",
        "media_content_type": "",
        "media_content_id": "media-source://system_bridge",
        "children_media_class": "directory",
        "can_play": False,
        "can_expand": True,
        "thumbnail": None,
        "not_shown": 0,
        "children": [
            {
                "title": "TestSystem",
                "media_class": "directory",
                "media_content_type": "",
                "media_content_id": f"media-source://system_bridge/{device.id}",
                "children_media_class": "directory",
                "can_play": False,
                "can_expand": True,
                "thumbnail": None,
            }
        ],
    }
