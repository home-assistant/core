"""Tests for metoffice init."""

from __future__ import annotations

import datetime

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, METOFFICE_CONFIG_WAVERTREE, TEST_COORDINATES_WAVERTREE

from tests.common import MockConfigEntry


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
@pytest.mark.parametrize(
    ("old_unique_id", "new_unique_id", "migration_needed"),
    [
        (
            f"weather_{TEST_COORDINATES_WAVERTREE}",
            f"significantWeatherCode_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"temperature_{TEST_COORDINATES_WAVERTREE}",
            f"screenTemperature_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"feels_like_temperature_{TEST_COORDINATES_WAVERTREE}",
            f"feelsLikeTemperature_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"wind_speed_{TEST_COORDINATES_WAVERTREE}",
            f"windSpeed10m_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"wind_direction_{TEST_COORDINATES_WAVERTREE}",
            f"windDirectionFrom10m_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"wind_gust_{TEST_COORDINATES_WAVERTREE}",
            f"windGustSpeed10m_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"uv_{TEST_COORDINATES_WAVERTREE}",
            f"uvIndex_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"precipitation_{TEST_COORDINATES_WAVERTREE}",
            f"probOfPrecipitation_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"humidity_{TEST_COORDINATES_WAVERTREE}",
            f"screenRelativeHumidity_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"name_{TEST_COORDINATES_WAVERTREE}",
            f"name_{TEST_COORDINATES_WAVERTREE}",
            False,
        ),
        ("abcde", "abcde", False),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    old_unique_id: str,
    new_unique_id: str,
    migration_needed: bool,
) -> None:
    """Test unique id migration."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        suggested_object_id="my_sensor",
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    if migration_needed:
        assert (
            entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id)
            is None
        )

    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, new_unique_id)
        == "sensor.my_sensor"
    )
