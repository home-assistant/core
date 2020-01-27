"""Tests for Vizio init."""
import pytest

from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN
from homeassistant.helpers.typing import HomeAssistantType

from .const import MOCK_SPEAKER_CONFIG_ENTRY


async def test_unload(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test loading component and unloading entry."""
    await hass.config_entries.async_add(MOCK_SPEAKER_CONFIG_ENTRY)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 1

    assert await hass.config_entries.async_unload(MOCK_SPEAKER_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 0
