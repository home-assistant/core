"""Tests for Vizio init."""
import pytest

from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN
from homeassistant.components.vizio.const import DOMAIN
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from .const import MOCK_USER_VALID_TV_CONFIG, UNIQUE_ID

from tests.common import MockConfigEntry


async def test_setup_component(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test component setup."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: MOCK_USER_VALID_TV_CONFIG}
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 1


async def test_load_and_unload(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test loading and unloading entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 1

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 0
