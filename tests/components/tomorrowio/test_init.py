"""Tests for Tomorrow.io init."""
import logging

import pytest

from homeassistant.components.tomorrowio.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.tomorrowio.const import DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from .const import MIN_CONFIG

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

NEW_NAME = "New Name"


async def test_load_and_unload(
    hass: HomeAssistant,
    tomorrowio_config_entry_update: pytest.fixture,
) -> None:
    """Test loading and unloading entry."""
    data = _get_config_schema(hass, SOURCE_USER)(MIN_CONFIG)
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=data, unique_id=_get_unique_id(hass, data), version=1
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 1

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 0
