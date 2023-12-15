"""Test the World Air Quality Index (WAQI) sensor."""
import json
from unittest.mock import patch

from aiowaqi import WAQIAirQuality, WAQIError, WAQISearchResult
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.waqi.const import CONF_STATION_NUMBER, DOMAIN
from homeassistant.components.waqi.sensor import CONF_LOCATIONS, CONF_STATIONS, SENSORS
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

LEGACY_CONFIG = {
    Platform.SENSOR: [
        {
            CONF_PLATFORM: DOMAIN,
            CONF_TOKEN: "asd",
            CONF_LOCATIONS: ["utrecht"],
            CONF_STATIONS: [6332],
        }
    ]
}


async def test_legacy_migration(hass: HomeAssistant) -> None:
    """Test migration from yaml to config flow."""
    search_result_json = json.loads(load_fixture("waqi/search_result.json"))
    search_results = [
        WAQISearchResult.from_dict(search_result)
        for search_result in search_result_json
    ]
    with patch(
        "aiowaqi.WAQIClient.search",
        return_value=search_results,
    ), patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        return_value=WAQIAirQuality.from_dict(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        assert await async_setup_component(hass, Platform.SENSOR, LEGACY_CONFIG)
        await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == 1


async def test_legacy_migration_already_imported(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test migration from yaml to config flow after already imported."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        return_value=WAQIAirQuality.from_dict(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    state = hass.states.get("sensor.de_jongweg_utrecht_air_quality_index")
    assert state.state == "29"

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_STATION_NUMBER: 4584,
                CONF_NAME: "xyz",
                CONF_API_KEY: "asd",
            },
        )
    )
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == 1


async def test_sensor_id_migration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test migrating unique id for original sensor."""
    mock_config_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN, DOMAIN, 4584, config_entry=mock_config_entry
    )
    with patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        return_value=WAQIAirQuality.from_dict(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 12
    assert hass.states.get("sensor.waqi_4584")
    assert hass.states.get("sensor.de_jongweg_utrecht_air_quality_index") is None
    assert entities[0].unique_id == "4584_air_quality"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test failed update."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        return_value=WAQIAirQuality.from_dict(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    entity_registry = er.async_get(hass)
    for sensor in SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"4584_{sensor.key}"
        )
        assert hass.states.get(entity_id) == snapshot


async def test_updating_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test failed update."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        side_effect=WAQIError(),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY
