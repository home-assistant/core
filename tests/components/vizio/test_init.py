"""Tests for Vizio init."""
from datetime import timedelta

import pytest

from homeassistant.components.vizio.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .const import MOCK_SPEAKER_CONFIG, MOCK_USER_VALID_TV_CONFIG, UNIQUE_ID

from tests.common import MockConfigEntry, async_fire_time_changed


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
    assert len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)) == 1


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
    assert len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)) == 1
    assert DOMAIN in hass.data

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids(Platform.MEDIA_PLAYER)
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
    assert len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)) == 1
    assert DOMAIN in hass.data

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids(Platform.MEDIA_PLAYER)
    assert len(entities) == 1
    for entity in entities:
        assert hass.states.get(entity).state == STATE_UNAVAILABLE
    assert DOMAIN not in hass.data


async def test_coordinator_update_failure(
    hass: HomeAssistant,
    vizio_connect: pytest.fixture,
    vizio_bypass_update: pytest.fixture,
    vizio_data_coordinator_update_failure: pytest.fixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator update failure after 10 days."""
    now = dt_util.now()
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)) == 1
    assert DOMAIN in hass.data

    # Failing 25 days in a row should result in a single log message
    # (first one after 10 days, next one would be at 30 days)
    for days in range(1, 25):
        async_fire_time_changed(hass, now + timedelta(days=days))
        await hass.async_block_till_done()

    err_msg = "Unable to retrieve the apps list from the external server"
    assert len([record for record in caplog.records if err_msg in record.msg]) == 1
