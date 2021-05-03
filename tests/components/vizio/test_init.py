"""Tests for Vizio init."""
import pytest

from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN
from homeassistant.components.vizio.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MOCK_SPEAKER_CONFIG, MOCK_USER_VALID_TV_CONFIG, UNIQUE_ID

from tests.common import MockConfigEntry


async def test_setup_component(
    hass: HomeAssistant,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test component setup."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: MOCK_USER_VALID_TV_CONFIG}
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 1


async def test_tv_load_and_unload(
    hass: HomeAssistant,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test loading and unloading TV entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 1
    assert DOMAIN in hass.data

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids(MP_DOMAIN)
    assert len(entities) == 1
    for entity in entities:
        assert hass.states.get(entity).state == STATE_UNAVAILABLE
    assert DOMAIN not in hass.data


async def test_speaker_load_and_unload(
    hass: HomeAssistant,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test loading and unloading speaker entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 1
    assert DOMAIN in hass.data

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids(MP_DOMAIN)
    assert len(entities) == 1
    for entity in entities:
        assert hass.states.get(entity).state == STATE_UNAVAILABLE
    assert DOMAIN not in hass.data
