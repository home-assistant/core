"""Tests for Climacell init."""
import logging

import pytest

from homeassistant.components.climacell.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.climacell.const import CONF_TIMESTEP, DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.const import CONF_API_VERSION
from homeassistant.helpers.typing import HomeAssistantType

from .const import MIN_CONFIG, V1_ENTRY_DATA

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_load_and_unload(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test loading and unloading entry."""
    data = _get_config_schema(hass)(MIN_CONFIG)
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        unique_id=_get_unique_id(hass, data),
        version=2,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 1

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 0


async def test_v3_load_and_unload(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test loading and unloading v3 entry."""
    data = _get_config_schema(hass)({**MIN_CONFIG, CONF_API_VERSION: 3})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        unique_id=_get_unique_id(hass, data),
        version=2,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 1

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 0


async def test_migrate_timestep_1(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test migration to timestep 1."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=V1_ENTRY_DATA,
        options={CONF_TIMESTEP: 2},
        unique_id=_get_unique_id(hass, V1_ENTRY_DATA),
        version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.version == 2
    assert (
        CONF_API_VERSION in config_entry.data
        and config_entry.data[CONF_API_VERSION] == 3
    )
    assert config_entry.options[CONF_TIMESTEP] == 1


async def test_migrate_timestep_5(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test migration to timestep 5."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=V1_ENTRY_DATA,
        options={CONF_TIMESTEP: 7},
        unique_id=_get_unique_id(hass, V1_ENTRY_DATA),
        version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.version == 2
    assert (
        CONF_API_VERSION in config_entry.data
        and config_entry.data[CONF_API_VERSION] == 3
    )
    assert config_entry.options[CONF_TIMESTEP] == 5


async def test_migrate_timestep_15(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test migration to timestep 15."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=V1_ENTRY_DATA,
        options={CONF_TIMESTEP: 20},
        unique_id=_get_unique_id(hass, V1_ENTRY_DATA),
        version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.version == 2
    assert (
        CONF_API_VERSION in config_entry.data
        and config_entry.data[CONF_API_VERSION] == 3
    )
    assert config_entry.options[CONF_TIMESTEP] == 15


async def test_migrate_timestep_30(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test migration to timestep 30."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=V1_ENTRY_DATA,
        options={CONF_TIMESTEP: 21},
        unique_id=_get_unique_id(hass, V1_ENTRY_DATA),
        version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.version == 2
    assert (
        CONF_API_VERSION in config_entry.data
        and config_entry.data[CONF_API_VERSION] == 3
    )
    assert config_entry.options[CONF_TIMESTEP] == 30
