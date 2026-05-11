"""Tests for the Data Grand Lyon sensor platform."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from data_grand_lyon_ha import TclPassage, TclPassageType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.data_grand_lyon.const import (
    CONF_LINE,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEPARTURES

from tests.common import MockConfigEntry, snapshot_platform

TZ_PARIS = ZoneInfo("Europe/Paris")


# Stop sensor tests


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test all sensor entities (state, attributes, registry)."""
    with patch("homeassistant.components.data_grand_lyon.PLATFORMS", [Platform.SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_stop_sensor_secondary_departure_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that direction/type sensors past the first departure are disabled by default."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in (
        "sensor.c3_stop_100_next_departure_2_direction",
        "sensor.c3_stop_100_next_departure_2_type",
        "sensor.c3_stop_100_next_departure_3_direction",
        "sensor.c3_stop_100_next_departure_3_type",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # First departure's direction and type stay enabled by default
    for entity_id in (
        "sensor.c3_stop_100_next_departure_1_direction",
        "sensor.c3_stop_100_next_departure_1_type",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.disabled_by is None


async def test_stop_sensor_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that sensors with no departure data return unknown."""
    mock_tcl_client.get_tcl_passages.return_value = []
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.c3_stop_100_next_departure_1")
    assert state is not None
    assert state.state == "unknown"


async def test_stop_sensor_aware_datetime_passthrough(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that already timezone-aware datetimes are passed through unchanged."""
    aware_departure = TclPassage(
        id=100,
        ligne="C3",
        direction="Gare Part-Dieu",
        delai_passage="3 min",
        type=TclPassageType.ESTIMATED,
        heure_passage=datetime(2026, 4, 10, 14, 3, tzinfo=TZ_PARIS),
        id_tarret_destination=0,
        course_theorique="A",
    )
    mock_tcl_client.get_tcl_passages.return_value = [aware_departure]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.c3_stop_100_next_departure_1")
    assert state is not None
    # Already aware at CEST (UTC+2), stored as UTC 12:03
    assert state.state == datetime(2026, 4, 10, 12, 3, tzinfo=UTC).isoformat()


# Coordinator error handling tests


async def test_coordinator_stop_fetch_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test coordinator handles stop fetch errors gracefully."""
    mock_tcl_client.get_tcl_passages.side_effect = ConnectionError("API down")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Single subentry fails → UpdateFailed → entry not loaded, sensors unavailable
    state = hass.states.get("sensor.c3_stop_100_next_departure_1")
    assert state is None


async def test_coordinator_partial_failure(
    hass: HomeAssistant,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test coordinator succeeds when one stop subentry fails but another succeeds."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=[
            ConfigSubentryData(
                data={CONF_LINE: "C3", CONF_STOP_ID: 100},
                subentry_id="stop_1",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="C3 - Stop 100",
                unique_id="C3_100",
            ),
            ConfigSubentryData(
                data={CONF_LINE: "T1", CONF_STOP_ID: 200},
                subentry_id="stop_2",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="T1 - Stop 200",
                unique_id="T1_200",
            ),
        ],
    )
    # First stop fails, second succeeds
    mock_tcl_client.get_tcl_passages.side_effect = [
        ConnectionError("API down"),
        MOCK_DEPARTURES,
    ]

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # stop_2 sensors should work
    state = hass.states.get("sensor.t1_stop_200_next_departure_1")
    assert state is not None
    assert state.state != "unavailable"
