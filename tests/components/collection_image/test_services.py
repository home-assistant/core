"""Tests for the Collection Image integration services."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.components.collection_image.image import CollectionImageImageEntity
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .const import DEFAULT_ENTITY_ID

from tests.common import MockConfigEntry


async def _setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the Collection Image integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_shuffle_action(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_media_source,
) -> None:
    """Test that shuffle calls get_random_image on the target entity."""
    await _setup_integration(hass, config_entry)

    with patch.object(
        CollectionImageImageEntity,
        "get_random_image",
        new_callable=AsyncMock,
    ) as mock_get_random_image:
        await hass.services.async_call(
            DOMAIN,
            "shuffle",
            {ATTR_ENTITY_ID: DEFAULT_ENTITY_ID},
            blocking=True,
        )

    mock_get_random_image.assert_awaited_once()
