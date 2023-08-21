"""Test the World Air Quality Index (WAQI) sensor."""
import json
from unittest.mock import patch

from aiowaqi import WAQIAirQuality, WAQIError, WAQISearchResult

from homeassistant.components.waqi.const import CONF_STATION_NUMBER, DOMAIN
from homeassistant.components.waqi.sensor import CONF_LOCATIONS, CONF_STATIONS
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
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
        WAQISearchResult.parse_obj(search_result)
        for search_result in search_result_json
    ]
    with patch(
        "aiowaqi.WAQIClient.search",
        return_value=search_results,
    ), patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        return_value=WAQIAirQuality.parse_obj(
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
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    state = hass.states.get("sensor.waqi_de_jongweg_utrecht")
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


async def test_sensor(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test failed update."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        return_value=WAQIAirQuality.parse_obj(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    state = hass.states.get("sensor.waqi_de_jongweg_utrecht")
    assert state.state == "29"


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
