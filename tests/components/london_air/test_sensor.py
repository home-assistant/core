"""Tests for the London Air sensor platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.london_air.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.london_air.coordinator import NO_SPECIES_DATA
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test the sensor reports the authority air quality band."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "Low"
    assert state.attributes["icon"] == "mdi:cloud-outline"
    assert state.attributes["sites"] == 2
    assert state.attributes["updated"] == "2017-08-03 03:00:00"
    data = state.attributes["data"]
    assert len(data) == 2
    assert data[0]["site_code"] == "ME2"
    assert data[0]["site_name"] == "Merton Road"
    assert data[0]["pollutants"][0]["code"] == "PM10"
    assert data[0]["pollutants"][0]["summary"] == "PM10 is Low"

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 1
    assert device_entries[0].entry_type is dr.DeviceEntryType.SERVICE


async def test_sensor_no_species_sentinel(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Test a site with no species data preserves the legacy sentinel."""
    payload = {
        "HourlyAirQualityIndex": {
            "LocalAuthority": [
                {
                    "@LocalAuthorityName": "Merton",
                    "Site": [
                        {
                            "@BulletinDate": "2017-08-03 03:00:00",
                            "@SiteCode": "ME1",
                            "@SiteName": "Merton - Test Site",
                            "@SiteType": "Roadside",
                            "@Latitude": "51.4",
                            "@Longitude": "-0.1",
                            "Species": [],
                        }
                    ],
                }
            ]
        }
    }
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=payload)
    mock_session.get.return_value = response

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "unknown"
    data = state.attributes["data"]
    assert data[0]["pollutants"] == [NO_SPECIES_DATA]
    assert data[0]["pollutants_status"] == NO_SPECIES_DATA
    assert data[0]["number_of_pollutants"] == 0


async def test_sensor_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test the sensor becomes unavailable when a refresh fails."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientConnectorError(Mock(), OSError("test"))
        )
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "unavailable"


async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Test setup retries when the API is unavailable."""
    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientConnectorError(Mock(), OSError("test"))
        )
    )

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_yaml_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test YAML setup imports a config entry and keeps the legacy entity IDs."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "london_air",
                "locations": ["Merton", "City of London"],
            }
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == DOMAIN
    assert entries[0].data["locations"] == ["Merton", "City of London"]

    assert (
        len(er.async_entries_for_config_entry(entity_registry, entries[0].entry_id))
        == 2
    )

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "Low"

    assert hass.states.get("sensor.city_of_london") is not None


async def test_yaml_migration_import_failure(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_session: MagicMock,
) -> None:
    """Test YAML setup registers a repair issue when the import fails."""
    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientConnectorError(Mock(), OSError("test"))
        )
    )

    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "london_air", "locations": ["Merton"]}},
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0

    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )

    assert hass.states.get("sensor.merton") is None


async def test_yaml_migration_existing_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test YAML setup with an existing entry does not create duplicates."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "london_air", "locations": ["Merton"]}},
    )
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert (
        len(er.async_entries_for_config_entry(entity_registry, entries[0].entry_id))
        == 1
    )

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
