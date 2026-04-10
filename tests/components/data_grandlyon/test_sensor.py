"""Tests for the Data Grand Lyon sensor platform."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from data_grand_lyon_ha import (
    TclPassage,
    TclPassageType,
    VelovAvailabilityLevel,
    VelovBikeStandAvailability,
    VelovStation,
    VelovStationStatus,
)
import pytest

from homeassistant.components.data_grandlyon.const import (
    CONF_LINE,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TZ_PARIS = ZoneInfo("Europe/Paris")

MOCK_PASSAGES = [
    TclPassage(
        id=100,
        ligne="C3",
        direction="Gare Part-Dieu",
        delai_passage="3 min",
        type=TclPassageType.ESTIMATED,
        heure_passage=datetime(2026, 4, 10, 14, 3),
        id_tarret_destination=0,
        course_theorique="A",
    ),
    TclPassage(
        id=100,
        ligne="C3",
        direction="Gare St-Paul",
        delai_passage="8 min",
        type=TclPassageType.THEORETICAL,
        heure_passage=datetime(2026, 4, 10, 14, 8),
        id_tarret_destination=0,
        course_theorique="B",
    ),
]

MOCK_VELOV_STATION = VelovStation(
    number=1002,
    name="Gare Part-Dieu",
    address="Place Charles Béraudier",
    commune="Lyon",
    status=VelovStationStatus.OPEN,
    availability=VelovAvailabilityLevel.GREEN,
    lat=45.76,
    lng=4.86,
    bike_stands=20,
    available_bikes=12,
    available_bike_stands=8,
    banking=True,
    last_update=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
    total_stands=VelovBikeStandAvailability(
        bikes=12,
        electrical_bikes=5,
        electrical_internal_battery_bikes=3,
        electrical_removable_battery_bikes=2,
        mechanical_bikes=7,
        stands=8,
        capacity=20,
    ),
)


@pytest.fixture
def mock_config_entry_with_stop() -> MockConfigEntry:
    """Create a config entry with a stop subentry."""
    return MockConfigEntry(
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
            )
        ],
    )


@pytest.fixture
def mock_config_entry_with_velov() -> MockConfigEntry:
    """Create a config entry with a Vélo'v subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Data Grand Lyon",
        data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        subentries_data=[
            ConfigSubentryData(
                data={CONF_STATION_ID: 1002},
                subentry_id="velov_1",
                subentry_type=SUBENTRY_TYPE_VELOV,
                title="Gare Part-Dieu",
                unique_id="1002",
            )
        ],
    )


@pytest.fixture
def mock_tcl_client() -> Generator[AsyncMock]:
    """Mock DataGrandLyonClient for coordinator."""
    with patch(
        "homeassistant.components.data_grandlyon.DataGrandLyonClient", autospec=True
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_tcl_passages.return_value = MOCK_PASSAGES
        client.get_velov_station.return_value = MOCK_VELOV_STATION
        yield client


# Stop sensor tests


async def test_stop_sensor_native_value_timezone(
    hass: HomeAssistant,
    mock_config_entry_with_stop: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that naive datetimes are localized to Europe/Paris."""
    mock_config_entry_with_stop.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.c3_stop_100_next_passage_1")
    assert state is not None
    # Naive 14:03 localized to Europe/Paris (CEST = UTC+2) → stored as UTC 12:03
    assert state.state == datetime(2026, 4, 10, 12, 3, tzinfo=UTC).isoformat()


async def test_stop_sensor_icon_estimated(
    hass: HomeAssistant,
    mock_config_entry_with_stop: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that estimated passages get the check-outline icon."""
    mock_config_entry_with_stop.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop.entry_id)
    await hass.async_block_till_done()

    # First passage is ESTIMATED
    state = hass.states.get("sensor.c3_stop_100_next_passage_1")
    assert state is not None
    assert state.attributes["icon"] == "mdi:clock-check-outline"


async def test_stop_sensor_icon_theoretical(
    hass: HomeAssistant,
    mock_config_entry_with_stop: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that theoretical passages get the plain clock icon."""
    mock_config_entry_with_stop.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop.entry_id)
    await hass.async_block_till_done()

    # Second passage is THEORETICAL
    state = hass.states.get("sensor.c3_stop_100_next_passage_2")
    assert state is not None
    assert state.attributes["icon"] == "mdi:clock-outline"


async def test_stop_sensor_extra_attributes(
    hass: HomeAssistant,
    mock_config_entry_with_stop: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that line, direction, and type are exposed as attributes."""
    mock_config_entry_with_stop.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.c3_stop_100_next_passage_1")
    assert state is not None
    assert state.attributes["line"] == "C3"
    assert state.attributes["direction"] == "Gare Part-Dieu"
    assert state.attributes["type"] == "estimated"

    state2 = hass.states.get("sensor.c3_stop_100_next_passage_2")
    assert state2 is not None
    assert state2.attributes["type"] == "theoretical"


async def test_stop_sensor_no_data(
    hass: HomeAssistant,
    mock_config_entry_with_stop: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that sensors with no passage data return unknown."""
    mock_tcl_client.get_tcl_passages.return_value = []
    mock_config_entry_with_stop.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.c3_stop_100_next_passage_1")
    assert state is not None
    assert state.state == "unknown"


async def test_stop_sensor_third_passage_missing(
    hass: HomeAssistant,
    mock_config_entry_with_stop: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that the third passage sensor is unknown when only 2 passages exist."""
    mock_config_entry_with_stop.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop.entry_id)
    await hass.async_block_till_done()

    # Only 2 mock passages, third should be unknown
    state = hass.states.get("sensor.c3_stop_100_next_passage_3")
    assert state is not None
    assert state.state == "unknown"


# Vélo'v sensor tests


async def test_velov_sensor_available_bikes(
    hass: HomeAssistant,
    mock_config_entry_with_velov: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test Vélo'v available bikes sensor."""
    mock_config_entry_with_velov.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_velov.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gare_part_dieu_available_bikes")
    assert state is not None
    assert state.state == "12"


async def test_velov_sensor_electrical_bikes(
    hass: HomeAssistant,
    mock_config_entry_with_velov: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test Vélo'v electrical bikes sensor."""
    mock_config_entry_with_velov.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_velov.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gare_part_dieu_available_electrical_bikes")
    assert state is not None
    assert state.state == "5"


async def test_velov_sensor_mechanical_bikes(
    hass: HomeAssistant,
    mock_config_entry_with_velov: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test Vélo'v mechanical bikes sensor."""
    mock_config_entry_with_velov.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_velov.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gare_part_dieu_available_mechanical_bikes")
    assert state is not None
    assert state.state == "7"


async def test_velov_sensor_available_stands(
    hass: HomeAssistant,
    mock_config_entry_with_velov: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test Vélo'v available stands sensor."""
    mock_config_entry_with_velov.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_velov.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gare_part_dieu_available_bike_stands")
    assert state is not None
    assert state.state == "8"


async def test_stop_sensor_aware_datetime_passthrough(
    hass: HomeAssistant,
    mock_config_entry_with_stop: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that already timezone-aware datetimes are passed through unchanged."""
    aware_passage = TclPassage(
        id=100,
        ligne="C3",
        direction="Gare Part-Dieu",
        delai_passage="3 min",
        type=TclPassageType.ESTIMATED,
        heure_passage=datetime(2026, 4, 10, 14, 3, tzinfo=TZ_PARIS),
        id_tarret_destination=0,
        course_theorique="A",
    )
    mock_tcl_client.get_tcl_passages.return_value = [aware_passage]
    mock_config_entry_with_stop.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.c3_stop_100_next_passage_1")
    assert state is not None
    # Already aware at CEST (UTC+2), stored as UTC 12:03
    assert state.state == datetime(2026, 4, 10, 12, 3, tzinfo=UTC).isoformat()


async def test_velov_sensor_station_missing_from_data(
    hass: HomeAssistant,
    mock_config_entry_with_velov: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test Vélo'v sensor returns unknown when station is not in coordinator data."""
    mock_tcl_client.get_velov_station.return_value = None
    mock_config_entry_with_velov.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_velov.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gare_part_dieu_available_bikes")
    assert state is not None
    assert state.state == "unknown"


# Coordinator error handling tests


async def test_coordinator_stop_fetch_error(
    hass: HomeAssistant,
    mock_config_entry_with_stop: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test coordinator handles stop fetch errors gracefully."""
    mock_tcl_client.get_tcl_passages.side_effect = ConnectionError("API down")
    mock_config_entry_with_stop.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop.entry_id)
    await hass.async_block_till_done()

    # Single subentry fails → UpdateFailed → entry not loaded, sensors unavailable
    state = hass.states.get("sensor.c3_stop_100_next_passage_1")
    assert state is None or state.state == "unavailable"


async def test_coordinator_velov_fetch_error(
    hass: HomeAssistant,
    mock_config_entry_with_velov: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test coordinator handles Vélo'v fetch errors gracefully."""
    mock_tcl_client.get_velov_station.side_effect = ConnectionError("API down")
    mock_config_entry_with_velov.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_velov.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gare_part_dieu_available_bikes")
    assert state is None or state.state == "unavailable"


async def test_coordinator_partial_failure(
    hass: HomeAssistant,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test coordinator succeeds when one subentry fails but another succeeds."""
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
                data={CONF_STATION_ID: 1002},
                subentry_id="velov_1",
                subentry_type=SUBENTRY_TYPE_VELOV,
                title="Gare Part-Dieu",
                unique_id="1002",
            ),
        ],
    )
    # Stop fetch fails, but vélo'v succeeds
    mock_tcl_client.get_tcl_passages.side_effect = ConnectionError("API down")
    mock_tcl_client.get_velov_station.return_value = MOCK_VELOV_STATION

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Vélo'v sensors should work
    state = hass.states.get("sensor.gare_part_dieu_available_bikes")
    assert state is not None
    assert state.state == "12"


# Init update listener test


async def test_update_entry_reloads(
    hass: HomeAssistant,
    mock_config_entry_with_stop: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that the update listener triggers a reload."""
    mock_config_entry_with_stop.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_stop.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(
            mock_config_entry_with_stop, title="Updated Data Grand Lyon"
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(mock_config_entry_with_stop.entry_id)
