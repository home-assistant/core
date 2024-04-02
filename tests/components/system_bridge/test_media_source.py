"""Test the System Bridge integration."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths

from homeassistant.components.media_source import URI_SCHEME, async_browse_media
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FIXTURE_UUID, setup_integration

from tests.common import MockConfigEntry


async def test_async_browse_media(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: MagicMock,
) -> None:
    """Test async_browse_media."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Get device from device registry
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, FIXTURE_UUID)},
    )
    assert device is not None

    browse_media_root = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}",
    )

    assert browse_media_root.as_dict() == snapshot(
        name=f"{DOMAIN}_browse_media_root",
        exclude=paths("children", "media_content_id"),
    )

    # browse_media_entry = await async_browse_media(
    #     hass,
    #     f"{URI_SCHEME}{DOMAIN}~~{entry.entry_id}",
    # )

    # assert browse_media_entry.as_dict() == snapshot(name=f"{DOMAIN}_browse_media_entry")
