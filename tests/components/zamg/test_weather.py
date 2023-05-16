"""Test Zamg component weather."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.components.zamg.const import DOMAIN as ZAMG_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_CONFIG_ENTRY
from .conftest import TEST_STATION_ID, TEST_STATION_NAME

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entitydata", "unique_id"),
    [
        (
            {
                "domain": WEATHER_DOMAIN,
                "platform": ZAMG_DOMAIN,
                "unique_id": TEST_STATION_ID,
                "suggested_object_id": f"Zamg {TEST_STATION_NAME}",
                "disabled_by": None,
            },
            TEST_STATION_ID,
        ),
    ],
)
async def test_weather_1(
    hass: HomeAssistant,
    mock_zamg_coordinator: MagicMock,
    entitydata: dict,
    unique_id: str,
) -> None:
    """Test reading native temperature."""
    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        ZAMG_DOMAIN,
        unique_id=TEST_STATION_ID,
        suggested_object_id=f"Zamg {TEST_STATION_NAME}",
        config_entry=mock_config_entry,
    )

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == unique_id

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("weather.zamg_graz_flughafen"))

    assert state.attributes.get(ATTR_WEATHER_HUMIDITY) == 67
    assert state.attributes.get(ATTR_WEATHER_PRESSURE) == 1012.0
    assert state.attributes.get(ATTR_WEATHER_TEMPERATURE) == 22.6
    assert state.attributes.get(ATTR_WEATHER_WIND_BEARING) == 180
    assert state.attributes.get(ATTR_WEATHER_WIND_SPEED) == 14.51  # 4.03 m/s -> km/h


@pytest.mark.parametrize(
    ("entitydata", "unique_id"),
    [
        (
            {
                "domain": WEATHER_DOMAIN,
                "platform": ZAMG_DOMAIN,
                "unique_id": TEST_STATION_ID,
                "suggested_object_id": f"Zamg {TEST_STATION_NAME}",
                "disabled_by": None,
            },
            TEST_STATION_ID,
        ),
    ],
)
async def test_weather_2(
    hass: HomeAssistant,
    mock_zamg_coordinator2: MagicMock,
    entitydata: dict,
    unique_id: str,
) -> None:
    """Test reading native temperature."""
    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        ZAMG_DOMAIN,
        unique_id=TEST_STATION_ID,
        suggested_object_id=f"Zamg {TEST_STATION_NAME}",
        config_entry=mock_config_entry,
    )

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == unique_id

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("weather.zamg_graz_flughafen"))

    assert state.attributes.get(ATTR_WEATHER_HUMIDITY) == 67
    assert state.attributes.get(ATTR_WEATHER_PRESSURE) == 1012.0
    assert state.attributes.get(ATTR_WEATHER_TEMPERATURE) == 22.6
    assert state.attributes.get(ATTR_WEATHER_WIND_BEARING) == 180
    assert state.attributes.get(ATTR_WEATHER_WIND_SPEED) == 14.51  # 4.03 m/s -> km/h


@pytest.mark.parametrize(
    ("entitydata", "unique_id"),
    [
        (
            {
                "domain": WEATHER_DOMAIN,
                "platform": ZAMG_DOMAIN,
                "unique_id": TEST_STATION_ID,
                "suggested_object_id": f"Zamg {TEST_STATION_NAME}",
                "disabled_by": None,
            },
            TEST_STATION_ID,
        ),
    ],
)
async def test_weather_3(
    hass: HomeAssistant,
    mock_zamg_coordinator3: MagicMock,
    entitydata: dict,
    unique_id: str,
) -> None:
    """Test reading native temperature."""
    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        ZAMG_DOMAIN,
        unique_id=TEST_STATION_ID,
        suggested_object_id=f"Zamg {TEST_STATION_NAME}",
        config_entry=mock_config_entry,
    )

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == unique_id

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("weather.zamg_graz_flughafen"))

    assert state.attributes.get(ATTR_WEATHER_HUMIDITY) == 67
    assert state.attributes.get(ATTR_WEATHER_PRESSURE) == 1012.0
    assert state.attributes.get(ATTR_WEATHER_TEMPERATURE) is None
    assert state.attributes.get(ATTR_WEATHER_WIND_BEARING) is None
    assert state.attributes.get(ATTR_WEATHER_WIND_SPEED) is None
