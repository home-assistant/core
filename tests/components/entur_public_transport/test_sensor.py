"""Tests for the Entur public transport sensor platform."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.entur_public_transport.const import (
    ATTR_EXPECTED_AT,
    ATTR_NEXT_UP_AT,
    ATTR_NEXT_UP_DELAY,
    ATTR_NEXT_UP_IN,
    ATTR_NEXT_UP_REALTIME,
    ATTR_NEXT_UP_ROUTE,
    ATTR_NEXT_UP_ROUTE_ID,
    ATTR_ROUTE,
    DOMAIN,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

FIXED_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.mark.usefixtures("init_integration")
async def test_sensor(
    hass: HomeAssistant,
    mock_place: MagicMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor state and attributes via snapshot."""
    freezer.move_to(FIXED_TIME)
    mock_place.estimated_calls[0].expected_departure_time = FIXED_TIME + timedelta(
        minutes=5
    )

    await async_update_entity(hass, "sensor.entur_nsr_stopplace_548_bergen_stasjon")

    state = hass.states.get("sensor.entur_nsr_stopplace_548_bergen_stasjon")
    assert state == snapshot


async def test_sensor_unavailable_when_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
) -> None:
    """Test sensor is unavailable when no data."""
    mock_entur_client.get_stop_info.return_value = None
    mock_entur_client.all_stop_places_quays.return_value = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.entur_nsr_stopplace_548_bergen_stasjon")
    # No entities should be created if no stops are returned
    assert state is None


async def test_sensor_with_multiple_departures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
    mock_place: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor with multiple departures shows next departure info."""
    freezer.move_to(FIXED_TIME)

    # Create multiple estimated calls
    first_call = MagicMock()
    first_call.is_realtime = True
    first_call.expected_departure_time = FIXED_TIME + timedelta(minutes=5)
    first_call.front_display = "45 Voss"
    first_call.line_id = "NSB:Line:45"
    first_call.transport_mode = "rail"
    first_call.delay_in_min = 0

    second_call = MagicMock()
    second_call.is_realtime = False
    second_call.expected_departure_time = FIXED_TIME + timedelta(minutes=15)
    second_call.front_display = "60 Oslo"
    second_call.line_id = "NSB:Line:60"
    second_call.transport_mode = "rail"
    second_call.delay_in_min = 2

    mock_place.estimated_calls = [first_call, second_call]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.entur_nsr_stopplace_548_bergen_stasjon")
    assert state is not None

    # First departure
    assert state.attributes.get(ATTR_ROUTE) == "45 Voss"
    assert state.attributes.get(ATTR_EXPECTED_AT) is not None

    # Next departure
    assert state.attributes.get(ATTR_NEXT_UP_ROUTE) == "60 Oslo"
    assert state.attributes.get(ATTR_NEXT_UP_ROUTE_ID) == "NSB:Line:60"
    assert state.attributes.get(ATTR_NEXT_UP_AT) is not None
    assert state.attributes.get(ATTR_NEXT_UP_IN) is not None
    assert state.attributes.get(ATTR_NEXT_UP_REALTIME) is False
    assert state.attributes.get(ATTR_NEXT_UP_DELAY) == 2


async def test_sensor_no_estimated_calls(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
    mock_place: MagicMock,
) -> None:
    """Test sensor when there are no estimated calls."""
    mock_place.estimated_calls = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.entur_nsr_stopplace_548_bergen_stasjon")
    assert state is not None
    # State should be None/unknown when no departures
    assert state.state == "unknown"
    # Icon should be default (bus) when no calls
    assert state.attributes.get("icon") == "mdi:bus"


async def test_sensor_with_three_or_more_departures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
    mock_place: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor with 3+ departures shows additional departure info."""
    freezer.move_to(FIXED_TIME)

    # Create multiple estimated calls
    first_call = MagicMock()
    first_call.is_realtime = True
    first_call.expected_departure_time = FIXED_TIME + timedelta(minutes=5)
    first_call.front_display = "45 Voss"
    first_call.line_id = "NSB:Line:45"
    first_call.transport_mode = "rail"
    first_call.delay_in_min = 0

    second_call = MagicMock()
    second_call.is_realtime = True
    second_call.expected_departure_time = FIXED_TIME + timedelta(minutes=15)
    second_call.front_display = "60 Oslo"
    second_call.line_id = "NSB:Line:60"
    second_call.transport_mode = "rail"
    second_call.delay_in_min = 0

    third_call = MagicMock()
    third_call.is_realtime = True
    third_call.expected_departure_time = FIXED_TIME + timedelta(minutes=25)
    third_call.front_display = "70 Trondheim"
    third_call.line_id = "NSB:Line:70"
    third_call.transport_mode = "rail"
    third_call.delay_in_min = 0

    fourth_call = MagicMock()
    fourth_call.is_realtime = False  # Not realtime - should have "ca. " prefix
    fourth_call.expected_departure_time = FIXED_TIME + timedelta(minutes=35)
    fourth_call.front_display = "80 Stavanger"
    fourth_call.line_id = "NSB:Line:80"
    fourth_call.transport_mode = "rail"
    fourth_call.delay_in_min = 0

    mock_place.estimated_calls = [first_call, second_call, third_call, fourth_call]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.entur_nsr_stopplace_548_bergen_stasjon")
    assert state is not None

    # Check additional departures are present
    departure_3 = state.attributes.get("departure_#3")
    assert departure_3 is not None
    assert "70 Trondheim" in departure_3
    assert not departure_3.startswith("ca.")  # realtime, no prefix

    departure_4 = state.attributes.get("departure_#4")
    assert departure_4 is not None
    assert "80 Stavanger" in departure_4
    assert departure_4.startswith("ca.")  # not realtime, has prefix


YAML_CONFIG = {
    "sensor": {
        "platform": DOMAIN,
        "stop_ids": ["NSR:StopPlace:548"],
    }
}


async def test_yaml_import_success_creates_deprecation_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_entur_client: MagicMock,
) -> None:
    """Test successful YAML import creates a deprecation issue."""
    assert await async_setup_component(hass, "sensor", YAML_CONFIG)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_invalid_stop_id_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import with invalid stop ID creates specific issue."""
    config = {
        "sensor": {
            "platform": DOMAIN,
            "stop_ids": ["invalid_id"],
        }
    }
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_stop_id"
    )


async def test_yaml_import_cannot_connect_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_entur_client: MagicMock,
) -> None:
    """Test YAML import with connection failure creates specific issue."""
    mock_entur_client.update = AsyncMock(side_effect=TimeoutError)
    assert await async_setup_component(hass, "sensor", YAML_CONFIG)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )


async def test_yaml_import_unknown_error_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_entur_client: MagicMock,
) -> None:
    """Test YAML import with unknown error creates specific issue."""
    mock_entur_client.update = AsyncMock(side_effect=RuntimeError("unexpected"))
    assert await async_setup_component(hass, "sensor", YAML_CONFIG)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_unknown"
    )
