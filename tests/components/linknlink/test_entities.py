"""Tests for LinknLink sensor entities."""

from dataclasses import replace
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from aiolinknlink import UltraConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.linknlink.const import ENVIRONMENT_UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import ENVIRONMENT_STATE, MAC, TARGET_STATE, TARGET_UPDATE


def _distance_entity_ids(entity_registry: er.EntityRegistry) -> tuple[str, str]:
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
        "detected_people": "1",
        "people_in_zones": "0",
        "zone_1_people": "1",
        "zone_2_people": "0",
        "zone_3_people": "0",
        "zone_4_people": "0",
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
        f"{MAC}_detected_people",
        f"{MAC}_people_in_zones",
        f"{MAC}_temperature",
        f"{MAC}_wifi_signal",
        f"{MAC}_zone_1_people",
        f"{MAC}_zone_2_people",
        f"{MAC}_zone_3_people",
        f"{MAC}_zone_4_people",
    }
    assert mock_config_entry.runtime_data.data.environment_state is ENVIRONMENT_STATE
    zone_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_zone_3_people"
    )
    assert hass.states.get(zone_id).name == "eMotion Ultra People in zone 3"


async def test_target_updates_and_availability(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_target_subscription: tuple[MagicMock, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test distance updates, stale data, and subscription availability."""
    caplog.set_level(logging.INFO, logger="homeassistant.components.linknlink")
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_target_subscription
    target_callback = subscription_class.call_args.kwargs["callback"]
    status_callback = subscription_class.call_args.kwargs["status_callback"]
    horizontal_id, distance_id = _distance_entity_ids(entity_registry)
    detected_people_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_detected_people"
    )

    subscription.state = TARGET_STATE
    target_callback(TARGET_UPDATE)
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == "0.5"
    assert hass.states.get(distance_id).state == "1.3"

    status_callback(replace(TARGET_STATE, stale=True))
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == STATE_UNAVAILABLE
    assert hass.states.get(distance_id).state == STATE_UNAVAILABLE
    assert hass.states.get(detected_people_id).state == STATE_UNAVAILABLE

    status_callback(replace(TARGET_STATE, subscribed=False, last_error="offline"))
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == STATE_UNAVAILABLE
    assert hass.states.get(distance_id).state == STATE_UNAVAILABLE

    subscription.state = TARGET_STATE
    target_callback(TARGET_UPDATE)
    status_callback(TARGET_STATE)
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == "0.5"
    assert hass.states.get(distance_id).state == "1.3"
    assert caplog.text.count("radar target subscription is unavailable") == 1
    assert caplog.text.count("radar target subscription is available") == 1
    assert all(
        record.levelno == logging.INFO
        for record in caplog.records
        if "radar target subscription is" in record.message
    )


async def test_target_status_logs_only_real_transitions(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_target_subscription: tuple[MagicMock, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test initial setup is not logged as a recovered radar target subscription."""
    subscription_class, subscription = mock_target_subscription

    async def _async_start() -> None:
        status_callback = subscription_class.call_args.kwargs["status_callback"]
        status_callback(
            replace(
                TARGET_STATE,
                subscribed=False,
                stale=True,
                confirmation_count=0,
                latest_update=None,
                last_error=None,
            )
        )

    subscription.start.side_effect = _async_start
    caplog.set_level(logging.INFO, logger="homeassistant.components.linknlink")

    await setup_integration(hass, mock_config_entry)
    status_callback = subscription_class.call_args.kwargs["status_callback"]
    assert "radar target subscription is available" not in caplog.text

    status_callback(replace(TARGET_STATE, subscribed=False, last_error="offline"))
    status_callback(TARGET_STATE)
    await hass.async_block_till_done()

    assert caplog.text.count("radar target subscription is unavailable") == 1
    assert caplog.text.count("radar target subscription is available") == 1


async def test_empty_target_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_target_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test a radar update reporting no targets."""
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_target_subscription
    target_callback = subscription_class.call_args.kwargs["callback"]
    horizontal_id, distance_id = _distance_entity_ids(entity_registry)
    detected_people_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_detected_people"
    )
    assert detected_people_id is not None
    empty_update = replace(TARGET_UPDATE, targets=())
    subscription.state = replace(TARGET_STATE, latest_update=empty_update)

    target_callback(empty_update)
    await hass.async_block_till_done()

    assert hass.states.get(horizontal_id).state == STATE_UNKNOWN
    assert hass.states.get(distance_id).state == STATE_UNKNOWN
    assert hass.states.get(detected_people_id).state == "0"


async def test_target_updates_are_coalesced(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_target_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test rapid radar target updates use the latest state at most once per second."""
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_target_subscription
    target_callback = subscription_class.call_args.kwargs["callback"]
    detected_people_id = entity_registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_detected_people"
    )
    assert detected_people_id is not None

    target_callback(TARGET_UPDATE)
    empty_update = replace(TARGET_UPDATE, targets=())
    subscription.state = replace(TARGET_STATE, latest_update=empty_update)
    target_callback(empty_update)
    await hass.async_block_till_done()
    assert hass.states.get(detected_people_id).state == "1"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass.states.get(detected_people_id).state == "0"


async def test_target_updates_do_not_reset_environment_refresh(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_target_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test radar target callbacks preserve the environmental refresh timer."""
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_target_subscription
    target_callback = subscription_class.call_args.kwargs["callback"]
    status_callback = subscription_class.call_args.kwargs["status_callback"]
    coordinator = mock_config_entry.runtime_data

    with patch.object(coordinator, "_schedule_refresh") as schedule_refresh:
        target_callback(TARGET_UPDATE)
        empty_update = replace(TARGET_UPDATE, targets=())
        subscription.state = replace(TARGET_STATE, latest_update=empty_update)
        target_callback(empty_update)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        status_callback(replace(TARGET_STATE, stale=True))
        await hass.async_block_till_done()

    schedule_refresh.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        UltraConnectionError("offline"),
        OSError("network unreachable"),
        TimeoutError(),
        ValueError("invalid response"),
    ],
)
async def test_poll_failure_marks_device_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """Test a failed poll makes all entities unavailable until it recovers."""
    await setup_integration(hass, mock_config_entry)
    entity_ids = [
        entry.entity_id
        for entry in entity_registry.entities.get_entries_for_config_entry_id(
            mock_config_entry.entry_id
        )
        if entry.disabled_by is None
    ]
    assert entity_ids

    mock_linknlink_client.get_environment_state.side_effect = error
    freezer.tick(ENVIRONMENT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not mock_config_entry.runtime_data.last_update_success
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_linknlink_client.get_environment_state.side_effect = None
    freezer.tick(ENVIRONMENT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.last_update_success
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_missing_environment_values_are_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
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

    freezer.tick(ENVIRONMENT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
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
