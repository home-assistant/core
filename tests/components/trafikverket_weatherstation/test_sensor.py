"""Test the Trafikverket Weatherstation sensor platform."""

from dataclasses import replace
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytrafikverket import WeatherStationInfoModel
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.trafikverket_weatherstation.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import ENTRY_CONFIG


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_without_modified_time(
    hass: HomeAssistant,
    get_data: WeatherStationInfoModel,
) -> None:
    """Test the modified time sensor is unknown when the station sends no time."""
    config_entry = MockConfigEntry(domain=DOMAIN, source=SOURCE_USER, data=ENTRY_CONFIG)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_weatherstation.coordinator.TrafikverketWeather.async_get_weather",
        return_value=replace(get_data, modified_time=None),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.arlanda_data_modified_time")
    assert state is not None
    assert state.state == STATE_UNKNOWN
