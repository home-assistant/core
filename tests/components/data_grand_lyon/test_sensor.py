"""Tests for the Data Grand Lyon sensor platform."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch
from zoneinfo import ZoneInfo

from aiohttp import ClientConnectionError, ClientResponseError
from data_grand_lyon_ha import TclPassage, TclPassageType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.data_grand_lyon.const import (
    CONF_LINE,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV_STATION,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntryState,
    ConfigSubentryData,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_VELOV_STATION

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
    """Test direction/type sensors past the first departure are disabled by default."""
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
    """Test that sensors are unavailable when no departure data is found."""
    mock_tcl_client.get_tcl_passages.return_value = []
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.c3_stop_100_next_departure_1")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


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
    """Test coordinator raises UpdateFailed on stop fetch error."""
    mock_tcl_client.get_tcl_passages.side_effect = ClientConnectionError("API down")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_stop_http_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test coordinator raises UpdateFailed on non-auth HTTP errors for stops."""
    mock_tcl_client.get_tcl_passages.side_effect = ClientResponseError(
        Mock(), (), status=500
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_velov_auth_error(
    hass: HomeAssistant,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test coordinator triggers reauth on Vélo'v auth failure."""
    mock_tcl_client.get_velov_stations.side_effect = ClientResponseError(
        Mock(), (), status=401
    )
    mock_velov_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_velov_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"].get("source") == SOURCE_REAUTH for flow in flows)


async def test_coordinator_velov_http_error(
    hass: HomeAssistant,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test coordinator raises UpdateFailed on non-auth HTTP errors for Vélo'v."""
    mock_tcl_client.get_velov_stations.side_effect = ClientResponseError(
        Mock(), (), status=500
    )
    mock_velov_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_velov_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_all_fetch_errors(
    hass: HomeAssistant,
    mock_tcl_client: AsyncMock,
    mock_velov_subentries: list[ConfigSubentryData],
    mock_subentries: list[ConfigSubentryData],
) -> None:
    """Test coordinator raises UpdateFailed when both APIs fail."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=mock_velov_subentries + mock_subentries,
    )
    mock_tcl_client.get_tcl_passages.side_effect = ClientConnectionError("API down")
    mock_tcl_client.get_velov_stations.side_effect = ClientConnectionError("API down")

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


# Vélo'v sensor tests


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_velov_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test all Vélo'v sensor entities (state, attributes, registry)."""
    with patch("homeassistant.components.data_grand_lyon.PLATFORMS", [Platform.SENSOR]):
        mock_velov_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_velov_config_entry.entry_id
    )


async def test_velov_sensor_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that secondary Vélo'v sensors are disabled by default."""
    mock_velov_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
    await hass.async_block_till_done()

    for unique_id in (
        "velov_1001-capacity",
        "velov_1001-electrical_internal_battery_bikes",
        "velov_1001-electrical_removable_battery_bikes",
    ):
        entry = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entry is not None, unique_id
        reg_entry = entity_registry.async_get(entry)
        assert reg_entry is not None, unique_id
        assert reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    for unique_id in (
        "velov_1001-available_bikes",
        "velov_1001-available_mechanical_bikes",
        "velov_1001-available_electrical_bikes",
        "velov_1001-available_stands",
    ):
        entry = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entry is not None, unique_id
        reg_entry = entity_registry.async_get(entry)
        assert reg_entry is not None, unique_id
        assert reg_entry.disabled_by is None


async def test_velov_sensor_no_data(
    hass: HomeAssistant,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that Vélo'v sensors are unavailable when station not found."""
    mock_tcl_client.get_velov_stations.return_value = []
    mock_velov_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.velo_v_1001_available_bikes")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_coordinator_velov_fetch_error(
    hass: HomeAssistant,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test coordinator raises UpdateFailed on Vélo'v fetch error."""
    mock_tcl_client.get_velov_stations.side_effect = ClientConnectionError("API down")
    mock_velov_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_velov_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_mixed_partial_failure(
    hass: HomeAssistant,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that when one coordinator fails at setup, the entry retries."""
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
                data={CONF_STATION_ID: 1001},
                subentry_id="velov_1",
                subentry_type=SUBENTRY_TYPE_VELOV_STATION,
                title="Vélo'v 1001",
                unique_id="velov_1001",
            ),
        ],
    )
    mock_tcl_client.get_tcl_passages.side_effect = ClientConnectionError("API down")
    mock_tcl_client.get_velov_stations.return_value = [MOCK_VELOV_STATION]

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
