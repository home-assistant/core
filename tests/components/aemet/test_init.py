"""Define tests for the AEMET OpenData init."""

from unittest.mock import patch

import pytest
import requests_mock

from homeassistant.components.aemet.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .util import aemet_requests_mock

from tests.common import MockConfigEntry

CONFIG = {
    CONF_NAME: "aemet",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 40.30403754,
    CONF_LONGITUDE: -3.72935236,
}


async def test_unload_entry(hass):
    """Test that the options form."""

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ), requests_mock.mock() as _m:
        aemet_requests_mock(_m)

        config_entry = MockConfigEntry(
            domain=DOMAIN, unique_id="aemet_unique_id", data=CONFIG
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "old_unique_id,new_unique_id",
    [
        # Sensors which should be migrated
        (
            "aemet_unique_id-forecast-daily-precipitation",
            "aemet_unique_id-forecast-daily-native_precipitation",
        ),
        (
            "aemet_unique_id-forecast-daily-temperature",
            "aemet_unique_id-forecast-daily-native_temperature",
        ),
        (
            "aemet_unique_id-forecast-daily-templow",
            "aemet_unique_id-forecast-daily-native_templow",
        ),
        (
            "aemet_unique_id-forecast-daily-wind_speed",
            "aemet_unique_id-forecast-daily-native_wind_speed",
        ),
        (
            "aemet_unique_id-forecast-hourly-precipitation",
            "aemet_unique_id-forecast-hourly-native_precipitation",
        ),
        (
            "aemet_unique_id-forecast-hourly-temperature",
            "aemet_unique_id-forecast-hourly-native_temperature",
        ),
        (
            "aemet_unique_id-forecast-hourly-templow",
            "aemet_unique_id-forecast-hourly-native_templow",
        ),
        (
            "aemet_unique_id-forecast-hourly-wind_speed",
            "aemet_unique_id-forecast-hourly-native_wind_speed",
        ),
        # Already migrated
        (
            "aemet_unique_id-forecast-daily-native_templow",
            "aemet_unique_id-forecast-daily-native_templow",
        ),
        # No migration needed
        (
            "aemet_unique_id-forecast-daily-condition",
            "aemet_unique_id-forecast-daily-condition",
        ),
    ],
)
async def test_migrate_unique_id_sensor(
    hass: HomeAssistant,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test migration of unique_id."""
    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ), requests_mock.mock() as _m:
        aemet_requests_mock(_m)
        config_entry = MockConfigEntry(
            domain=DOMAIN, unique_id="aemet_unique_id", data=CONFIG
        )
        config_entry.add_to_hass(hass)

        entity_registry = er.async_get(hass)
        entity: er.RegistryEntry = entity_registry.async_get_or_create(
            domain=SENSOR_DOMAIN,
            platform=DOMAIN,
            unique_id=old_unique_id,
            config_entry=config_entry,
        )
        assert entity.unique_id == old_unique_id
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_migrated = entity_registry.async_get(entity.entity_id)
        assert entity_migrated
        assert entity_migrated.unique_id == new_unique_id
