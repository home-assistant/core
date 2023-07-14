"""Tests for metoffice init."""
from __future__ import annotations

import datetime

import pytest
import requests_mock

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, METOFFICE_CONFIG_WAVERTREE, TEST_COORDINATES_WAVERTREE

from tests.common import MockConfigEntry


@pytest.mark.freeze_time(
    datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.timezone.utc)
)
@pytest.mark.parametrize(
    ("old_unique_id", "new_unique_id", "migration_needed"),
    [
        (
            f"Station Name_{TEST_COORDINATES_WAVERTREE}",
            f"name_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Weather_{TEST_COORDINATES_WAVERTREE}",
            f"weather_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Temperature_{TEST_COORDINATES_WAVERTREE}",
            f"temperature_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Feels Like Temperature_{TEST_COORDINATES_WAVERTREE}",
            f"feels_like_temperature_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Wind Speed_{TEST_COORDINATES_WAVERTREE}",
            f"wind_speed_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Wind Direction_{TEST_COORDINATES_WAVERTREE}",
            f"wind_direction_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Wind Gust_{TEST_COORDINATES_WAVERTREE}",
            f"wind_gust_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Visibility_{TEST_COORDINATES_WAVERTREE}",
            f"visibility_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Visibility Distance_{TEST_COORDINATES_WAVERTREE}",
            f"visibility_distance_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"UV Index_{TEST_COORDINATES_WAVERTREE}",
            f"uv_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Probability of Precipitation_{TEST_COORDINATES_WAVERTREE}",
            f"precipitation_{TEST_COORDINATES_WAVERTREE}",
            True,
        ),
        (
            f"Humidity_{TEST_COORDINATES_WAVERTREE}",
            f"humidity_{TEST_COORDINATES_WAVERTREE}",
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
    old_unique_id: str,
    new_unique_id: str,
    migration_needed: bool,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test unique id migration."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)

    ent_reg = er.async_get(hass)

    entity: er.RegistryEntry = ent_reg.async_get_or_create(
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
        assert ent_reg.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id) is None

    assert (
        ent_reg.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, new_unique_id)
        == "sensor.my_sensor"
    )
