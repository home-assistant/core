"""Tests for LinknLink sensor entities."""

from dataclasses import replace
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, MagicMock

from aiolinknlink import UltraConnectionError
import pytest

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import ENVIRONMENT_STATE, MAC, POSITION_STATE, POSITION_UPDATE

from tests.common import MockConfigEntry, async_fire_time_changed


def _position_entity_ids(entity_registry: er.EntityRegistry) -> tuple[str, str]:
    """Return the two distance sensor IDs."""
    horizontal_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_nearest_horizontal_distance"
    )
    distance_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_nearest_distance"
    )
    assert horizontal_id is not None
    assert distance_id is not None
    return horizontal_id, distance_id


async def test_sensor_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all sensors are registered with their initial states."""
    await setup_integration(hass, mock_config_entry)

    expected_states = {
        "nearest_horizontal_distance": "0.5",
        "nearest_distance": "1.3",
        "temperature": "23.5",
        "humidity": "48.25",
        "illuminance": "325.0",
        "target_count": "1",
        "persons_in_fenced_zones": "0",
        "zone_1_target_counts": "1",
        "zone_2_target_counts": "0",
        "zone_3_target_counts": "0",
        "zone_4_target_counts": "0",
    }
    for key, expected in expected_states.items():
        entity_id = entity_registry.async_get_entity_id(
            "sensor", "linknlink", f"{MAC}_{key}"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == expected

    wifi_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_wifi_signal"
    )
    assert wifi_id is not None
    assert hass.states.get(wifi_id) is None

    assert {
        entry.unique_id
        for entry in entity_registry.entities.get_entries_for_config_entry_id(
            mock_config_entry.entry_id
        )
    } == {
        f"{MAC}_humidity",
        f"{MAC}_illuminance",
        f"{MAC}_nearest_distance",
        f"{MAC}_nearest_horizontal_distance",
        f"{MAC}_persons_in_fenced_zones",
        f"{MAC}_target_count",
        f"{MAC}_temperature",
        f"{MAC}_wifi_signal",
        f"{MAC}_zone_1_target_counts",
        f"{MAC}_zone_2_target_counts",
        f"{MAC}_zone_3_target_counts",
        f"{MAC}_zone_4_target_counts",
    }
    assert mock_config_entry.runtime_data.environment_state is ENVIRONMENT_STATE


async def test_position_updates_and_availability(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test distance updates, stale data, and subscription availability."""
    caplog.set_level(logging.INFO, logger="homeassistant.components.linknlink")
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_position_subscription
    position_callback = subscription_class.call_args.kwargs["callback"]
    status_callback = subscription_class.call_args.kwargs["status_callback"]
    horizontal_id, distance_id = _position_entity_ids(entity_registry)

    subscription.state = POSITION_STATE
    position_callback(POSITION_UPDATE)
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == "0.5"
    assert hass.states.get(distance_id).state == "1.3"

    status_callback(replace(POSITION_STATE, stale=True))
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == STATE_UNKNOWN
    assert hass.states.get(distance_id).state == STATE_UNKNOWN

    status_callback(replace(POSITION_STATE, subscribed=False, last_error="offline"))
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == STATE_UNAVAILABLE
    assert hass.states.get(distance_id).state == STATE_UNAVAILABLE

    subscription.state = POSITION_STATE
    position_callback(POSITION_UPDATE)
    status_callback(POSITION_STATE)
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == "0.5"
    assert hass.states.get(distance_id).state == "1.3"
    assert caplog.text.count("position subscription is unavailable") == 1
    assert caplog.text.count("position subscription is available") == 1
    assert all(
        record.levelno == logging.INFO
        for record in caplog.records
        if "position subscription is" in record.message
    )


async def test_empty_position_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test a position update reporting no targets."""
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_position_subscription
    position_callback = subscription_class.call_args.kwargs["callback"]
    horizontal_id, distance_id = _position_entity_ids(entity_registry)
    target_count_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_target_count"
    )
    assert target_count_id is not None
    empty_update = replace(POSITION_UPDATE, targets=())
    subscription.state = replace(POSITION_STATE, latest_update=empty_update)

    position_callback(empty_update)
    await hass.async_block_till_done()

    assert hass.states.get(horizontal_id).state == STATE_UNKNOWN
    assert hass.states.get(distance_id).state == STATE_UNKNOWN
    assert hass.states.get(target_count_id).state == "0"


async def test_position_updates_are_coalesced(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test rapid position updates use the latest state at most once per second."""
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_position_subscription
    position_callback = subscription_class.call_args.kwargs["callback"]
    target_count_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_target_count"
    )
    assert target_count_id is not None

    position_callback(POSITION_UPDATE)
    empty_update = replace(POSITION_UPDATE, targets=())
    subscription.state = replace(POSITION_STATE, latest_update=empty_update)
    position_callback(empty_update)
    await hass.async_block_till_done()
    assert hass.states.get(target_count_id).state == "1"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass.states.get(target_count_id).state == "0"


async def test_environment_failure_does_not_disable_position_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test independent availability for the environment API."""
    await setup_integration(hass, mock_config_entry)
    temperature_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_temperature"
    )
    horizontal_id, _ = _position_entity_ids(entity_registry)
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
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test supported fields with omitted values remain available."""
    await setup_integration(hass, mock_config_entry)
    missing_keys = {"temperature", "humidity", "illuminance"}
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

    for key in missing_keys:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", "linknlink", f"{MAC}_{key}"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_missing_optional_sensor_cable_is_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
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
    for key in missing_keys:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", "linknlink", f"{MAC}_{key}"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_entities_registered_when_initial_environment_read_fails(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test stable entities and transition logging when the API is offline."""
    caplog.set_level(logging.INFO, logger="homeassistant.components.linknlink")
    mock_linknlink_client.get_environment_state.side_effect = UltraConnectionError(
        "offline"
    )

    await setup_integration(hass, mock_config_entry)
    for key in ("temperature", "zone_4_target_counts"):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", "linknlink", f"{MAC}_{key}"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    await mock_config_entry.runtime_data.async_refresh()
    mock_linknlink_client.get_environment_state.side_effect = None
    mock_linknlink_client.get_environment_state.return_value = ENVIRONMENT_STATE
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert caplog.text.count("Ultra environmental state is unavailable") == 1
    assert caplog.text.count("Ultra environmental state is available") == 1
    assert all(
        record.levelno == logging.INFO
        for record in caplog.records
        if "Ultra environmental state is" in record.message
    )
