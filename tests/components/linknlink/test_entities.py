"""Tests for the LinknLink target-position event entity."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

from aiolinknlink import UltraConnectionError, UltraRadarZRange
import pytest

from homeassistant.components.linknlink.number import (
    RADAR_NUMBER_DESCRIPTIONS,
    LinknLinkRadarNumber,
)
from homeassistant.components.linknlink.select import (
    RADAR_SELECT_DESCRIPTIONS,
    RADAR_SENSITIVITY_DESCRIPTION,
    LinknLinkRadarSelect,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import (
    ENVIRONMENT_STATE,
    MAC,
    POSITION_STATE,
    POSITION_UPDATE,
    RADAR_STATUS,
)

from tests.common import MockConfigEntry


def _position_entity_ids(hass: HomeAssistant) -> tuple[str, str, str]:
    """Return the two distance sensor IDs and target-position event ID."""
    registry = er.async_get(hass)
    horizontal_id = registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_nearest_horizontal_distance"
    )
    distance_id = registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_nearest_distance"
    )
    event_id = registry.async_get_entity_id(
        "event", "linknlink", f"{MAC}_target_position"
    )
    assert horizontal_id is not None
    assert distance_id is not None
    assert event_id is not None
    return horizontal_id, distance_id, event_id


async def test_event_entity_setup(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the two distance sensors and target-position event entity."""
    await setup_integration(hass, mock_config_entry)

    horizontal_id, distance_id, event_id = _position_entity_ids(hass)
    assert hass.states.get(horizontal_id).state == "0.5"
    assert hass.states.get(distance_id).state == "1.3"
    assert hass.states.get(event_id) is not None
    assert {
        entry.unique_id
        for entry in er.async_get(hass).entities.get_entries_for_config_entry_id(
            mock_config_entry.entry_id
        )
    } == {
        f"{MAC}_nearest_distance",
        f"{MAC}_nearest_horizontal_distance",
        f"{MAC}_humidity",
        f"{MAC}_illuminance",
        f"{MAC}_occupancy",
        f"{MAC}_persons_in_fenced_zones",
        f"{MAC}_radar_default_absence_delay",
        f"{MAC}_radar_height",
        f"{MAC}_radar_install_direction",
        f"{MAC}_radar_install_mode",
        f"{MAC}_radar_sensitivity",
        f"{MAC}_radar_trigger_speed",
        f"{MAC}_radar_z_maximum",
        f"{MAC}_radar_z_minimum",
        f"{MAC}_radar_zone_1_absence_delay",
        f"{MAC}_radar_zone_2_absence_delay",
        f"{MAC}_radar_zone_3_absence_delay",
        f"{MAC}_radar_zone_4_absence_delay",
        f"{MAC}_target_position",
        f"{MAC}_target_count",
        f"{MAC}_temperature",
        f"{MAC}_wifi_signal",
        f"{MAC}_zone_1_presence",
        f"{MAC}_zone_1_target_counts",
        f"{MAC}_zone_2_presence",
        f"{MAC}_zone_2_target_counts",
        f"{MAC}_zone_3_presence",
        f"{MAC}_zone_3_target_counts",
        f"{MAC}_zone_4_presence",
        f"{MAC}_zone_4_target_counts",
    }


async def test_position_event_and_availability(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test typed position events and subscription availability."""
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_position_subscription
    position_callback = subscription_class.call_args.kwargs["callback"]
    status_callback = subscription_class.call_args.kwargs["status_callback"]
    horizontal_id, distance_id, event_id = _position_entity_ids(hass)

    subscription.state = POSITION_STATE
    position_callback(POSITION_UPDATE)
    await hass.async_block_till_done()

    event_state = hass.states.get(event_id)
    assert event_state is not None
    assert event_state.attributes["event_type"] == "position_update"
    assert event_state.attributes["target_count"] == 1
    assert event_state.attributes["targets"] == [{"x": 0.3, "y": 0.4, "z": 1.2}]
    assert event_state.attributes["nearest_horizontal_distance"] == 0.5
    assert event_state.attributes["nearest_distance"] == 1.3
    assert hass.states.get(horizontal_id).state == "0.5"
    assert hass.states.get(distance_id).state == "1.3"

    status_callback(replace(POSITION_STATE, stale=True))
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == STATE_UNKNOWN
    assert hass.states.get(distance_id).state == STATE_UNKNOWN

    status_callback(replace(POSITION_STATE, subscribed=False, last_error="offline"))
    await hass.async_block_till_done()
    assert hass.states.get(event_id).state == STATE_UNAVAILABLE
    assert hass.states.get(horizontal_id).state == STATE_UNAVAILABLE
    assert hass.states.get(distance_id).state == STATE_UNAVAILABLE

    status_callback(POSITION_STATE)
    await hass.async_block_till_done()
    assert hass.states.get(event_id).state != STATE_UNAVAILABLE


async def test_radar_numbers(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test numeric radar configuration state, writes, and device read-backs."""
    _, subscription = mock_position_subscription
    subscription.set_radar_height.return_value = replace(RADAR_STATUS, height=250)
    subscription.set_radar_z_range.return_value = replace(
        RADAR_STATUS,
        z_range=UltraRadarZRange(minimum=-1.5, maximum=2.0),
    )
    subscription.set_radar_default_absence_delay.return_value = replace(
        RADAR_STATUS, default_absence_delay=75
    )
    subscription.set_radar_zone_absence_delay.return_value = replace(
        RADAR_STATUS, zone_absence_delays=(60, 95, 120, 180)
    )
    await setup_integration(hass, mock_config_entry)
    registry = er.async_get(hass)

    entity_ids = {
        key: registry.async_get_entity_id("number", "linknlink", f"{MAC}_{key}")
        for key in (
            "radar_height",
            "radar_z_minimum",
            "radar_z_maximum",
            "radar_default_absence_delay",
            "radar_zone_1_absence_delay",
            "radar_zone_2_absence_delay",
            "radar_zone_3_absence_delay",
            "radar_zone_4_absence_delay",
        )
    }
    assert all(entity_ids.values())
    assert hass.states.get(entity_ids["radar_height"]).state == "240"
    assert hass.states.get(entity_ids["radar_z_minimum"]).state == "-2.0"
    assert hass.states.get(entity_ids["radar_z_maximum"]).state == "2.0"
    assert hass.states.get(entity_ids["radar_default_absence_delay"]).state == "60"
    assert hass.states.get(entity_ids["radar_zone_2_absence_delay"]).state == "90"

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_ids["radar_height"], "value": 250},
        blocking=True,
    )
    subscription.set_radar_height.assert_awaited_once_with(250)
    assert hass.states.get(entity_ids["radar_height"]).state == "250"

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_ids["radar_z_minimum"], "value": -1.5},
        blocking=True,
    )
    subscription.set_radar_z_range.assert_awaited_once_with(-1.5, 2.0)
    assert hass.states.get(entity_ids["radar_z_minimum"]).state == "-1.5"

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_ids["radar_default_absence_delay"], "value": 75},
        blocking=True,
    )
    subscription.set_radar_default_absence_delay.assert_awaited_once_with(75)
    assert hass.states.get(entity_ids["radar_default_absence_delay"]).state == "75"

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_ids["radar_zone_2_absence_delay"], "value": 95},
        blocking=True,
    )
    subscription.set_radar_zone_absence_delay.assert_awaited_once_with(2, 95)
    assert hass.states.get(entity_ids["radar_zone_2_absence_delay"]).state == "95"


async def test_radar_number_errors(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test invalid numeric values and device write failures."""
    _, subscription = mock_position_subscription
    await setup_integration(hass, mock_config_entry)
    height = LinknLinkRadarNumber(
        mock_config_entry.runtime_data,
        RADAR_NUMBER_DESCRIPTIONS[0],
    )

    with pytest.raises(HomeAssistantError):
        await height.async_set_native_value(1.5)

    subscription.set_radar_height.side_effect = UltraConnectionError("offline")
    with pytest.raises(HomeAssistantError):
        await height.async_set_native_value(250)


async def test_environment_and_occupancy_entities(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test standard environment, count, and occupancy entities."""
    await setup_integration(hass, mock_config_entry)
    registry = er.async_get(hass)

    expected_states = {
        ("sensor", "temperature"): "23.5",
        ("sensor", "humidity"): "48.25",
        ("sensor", "illuminance"): "325.0",
        ("sensor", "wifi_signal"): "-52",
        ("sensor", "target_count"): "1",
        ("sensor", "persons_in_fenced_zones"): "0",
        ("sensor", "zone_1_target_counts"): "1",
        ("sensor", "zone_2_target_counts"): "0",
        ("sensor", "zone_3_target_counts"): "0",
        ("sensor", "zone_4_target_counts"): "0",
        ("binary_sensor", "occupancy"): STATE_ON,
        ("binary_sensor", "zone_1_presence"): STATE_OFF,
    }
    for (domain, key), expected in expected_states.items():
        entity_id = registry.async_get_entity_id(domain, "linknlink", f"{MAC}_{key}")
        assert entity_id is not None
        assert hass.states.get(entity_id).state == expected

    for zone in range(2, 5):
        entity_id = registry.async_get_entity_id(
            "binary_sensor", "linknlink", f"{MAC}_zone_{zone}_presence"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert mock_config_entry.runtime_data.environment_state is ENVIRONMENT_STATE


async def test_environment_failure_does_not_disable_position_entities(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test independent availability for the slow local state API."""
    await setup_integration(hass, mock_config_entry)
    registry = er.async_get(hass)
    temperature_id = registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_temperature"
    )
    horizontal_id, _, _ = _position_entity_ids(hass)
    assert temperature_id is not None

    mock_linknlink_client.get_environment_state.side_effect = UltraConnectionError(
        "offline"
    )
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(temperature_id).state == STATE_UNAVAILABLE
    assert hass.states.get(horizontal_id).state == "0.5"
    assert mock_config_entry.runtime_data.last_update_success


async def test_missing_environment_values_are_unknown(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test missing values remain available with an unknown state."""
    await setup_integration(hass, mock_config_entry)
    registry = er.async_get(hass)
    missing_keys = {"temperature", "humidity", "zone_1_presence"}
    mock_linknlink_client.get_environment_state.return_value = replace(
        ENVIRONMENT_STATE,
        values={
            key: value
            for key, value in ENVIRONMENT_STATE.values.items()
            if key not in missing_keys
        },
    )

    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    for domain, key in (
        ("sensor", "temperature"),
        ("sensor", "humidity"),
        ("binary_sensor", "zone_1_presence"),
    ):
        entity_id = registry.async_get_entity_id(domain, "linknlink", f"{MAC}_{key}")
        assert entity_id is not None
        assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_missing_optional_sensor_cable_is_unavailable(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test optional temperature and humidity hardware availability."""
    missing_keys = {"temperature", "humidity"}
    mock_linknlink_client.get_environment_state.return_value = replace(
        ENVIRONMENT_STATE,
        values={
            key: value
            for key, value in ENVIRONMENT_STATE.values.items()
            if key not in missing_keys
        },
        available_fields=ENVIRONMENT_STATE.available_fields - missing_keys,
    )

    await setup_integration(hass, mock_config_entry)
    registry = er.async_get(hass)

    for key in missing_keys:
        entity_id = registry.async_get_entity_id("sensor", "linknlink", f"{MAC}_{key}")
        assert entity_id is not None
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_entities_registered_when_initial_environment_read_fails(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stable entities when the environment API is initially offline."""
    mock_linknlink_client.get_environment_state.side_effect = UltraConnectionError(
        "offline"
    )

    await setup_integration(hass, mock_config_entry)
    registry = er.async_get(hass)

    for domain, key in (
        ("sensor", "temperature"),
        ("sensor", "zone_4_target_counts"),
        ("binary_sensor", "zone_4_presence"),
    ):
        entity_id = registry.async_get_entity_id(domain, "linknlink", f"{MAC}_{key}")
        assert entity_id is not None
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_radar_sensitivity_select_and_recovery(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test device-read sensitivity control and recovery refresh."""
    subscription_class, subscription = mock_position_subscription
    subscription.set_radar_sensitivity.return_value = replace(
        RADAR_STATUS,
        sensitivity=1,
    )
    await setup_integration(hass, mock_config_entry)
    entity_id = er.async_get(hass).async_get_entity_id(
        "select",
        "linknlink",
        f"{MAC}_radar_sensitivity",
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "level_2"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "level_1"},
        blocking=True,
    )

    subscription.set_radar_sensitivity.assert_awaited_once_with(1)
    assert hass.states.get(entity_id).state == "level_1"

    status_callback = subscription_class.call_args.kwargs["status_callback"]
    status_callback(replace(POSITION_STATE, subscribed=False, last_error="offline"))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    subscription.get_radar_status.side_effect = UltraConnectionError("offline")
    status_callback(POSITION_STATE)
    await hass.async_block_till_done()
    assert subscription.get_radar_status.await_count == 2
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    subscription.get_radar_status.side_effect = None
    subscription.get_radar_status.return_value = RADAR_STATUS
    status_callback(POSITION_STATE)
    await hass.async_block_till_done()
    assert subscription.get_radar_status.await_count == 3
    assert hass.states.get(entity_id).state == "level_2"


async def test_radar_sensitivity_select_errors(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test invalid options and device write failures."""
    _, subscription = mock_position_subscription
    await setup_integration(hass, mock_config_entry)
    entity = LinknLinkRadarSelect(
        mock_config_entry.runtime_data,
        RADAR_SENSITIVITY_DESCRIPTION,
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_select_option("invalid")

    subscription.set_radar_sensitivity.side_effect = UltraConnectionError("offline")
    with pytest.raises(HomeAssistantError):
        await entity.async_select_option("level_1")


async def test_additional_radar_selects(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test trigger speed and installation select read-backs."""
    _, subscription = mock_position_subscription
    subscription.set_radar_trigger_speed.return_value = replace(
        RADAR_STATUS, trigger_speed=2
    )
    subscription.set_radar_install_mode.return_value = replace(
        RADAR_STATUS, install_mode=1
    )
    subscription.set_radar_install_direction.return_value = replace(
        RADAR_STATUS, install_direction=0
    )
    await setup_integration(hass, mock_config_entry)
    registry = er.async_get(hass)

    trigger_id = registry.async_get_entity_id(
        "select", "linknlink", f"{MAC}_radar_trigger_speed"
    )
    mode_id = registry.async_get_entity_id(
        "select", "linknlink", f"{MAC}_radar_install_mode"
    )
    direction_id = registry.async_get_entity_id(
        "select", "linknlink", f"{MAC}_radar_install_direction"
    )
    assert trigger_id is not None
    assert mode_id is not None
    assert direction_id is not None
    assert hass.states.get(trigger_id).state == "level_1"
    assert hass.states.get(mode_id).state == "ceiling"
    assert hass.states.get(direction_id).state == "up"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": trigger_id, "option": "level_2"},
        blocking=True,
    )
    subscription.set_radar_trigger_speed.assert_awaited_once_with(2)
    assert hass.states.get(trigger_id).state == "level_2"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": mode_id, "option": "wall"},
        blocking=True,
    )
    subscription.set_radar_install_mode.assert_awaited_once_with(1)
    assert hass.states.get(mode_id).state == "wall"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": direction_id, "option": "down"},
        blocking=True,
    )
    subscription.set_radar_install_direction.assert_awaited_once_with(0)
    assert hass.states.get(direction_id).state == "down"


async def test_install_direction_sentinel_is_not_reported_as_valid(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Keep an unconfigured firmware sentinel writable but report no option."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.radar_status = replace(RADAR_STATUS, install_direction=100)
    entity = LinknLinkRadarSelect(
        coordinator,
        next(
            description
            for description in RADAR_SELECT_DESCRIPTIONS
            if description.key == "radar_install_direction"
        ),
    )

    assert entity.available
    assert entity.current_option is None


async def test_empty_position_event(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test a position update reporting no targets."""
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_position_subscription
    position_callback = subscription_class.call_args.kwargs["callback"]
    horizontal_id, distance_id, event_id = _position_entity_ids(hass)
    empty_update = replace(POSITION_UPDATE, targets=())
    subscription.state = replace(POSITION_STATE, latest_update=empty_update)

    position_callback(empty_update)
    await hass.async_block_till_done()

    event_state = hass.states.get(event_id)
    assert event_state is not None
    assert event_state.attributes["target_count"] == 0
    assert event_state.attributes["targets"] == []
    assert event_state.attributes["nearest_horizontal_distance"] is None
    assert event_state.attributes["nearest_distance"] is None
    assert hass.states.get(horizontal_id).state == STATE_UNKNOWN
    assert hass.states.get(distance_id).state == STATE_UNKNOWN
