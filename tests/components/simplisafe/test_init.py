"""Define tests for SimpliSafe setup."""

import asyncio
import copy
import logging
from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from simplipy.errors import (
    EndpointUnavailableError,
    InvalidCredentialsError,
    RequestError,
    SimplipyError,
    WebsocketError,
)
from simplipy.system.v3 import SystemV3
from simplipy.websocket import WebsocketEvent

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.simplisafe import DOMAIN, WEBSOCKET_RETRY_DELAY
from homeassistant.components.simplisafe.coordinator import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component


async def test_base_station_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    api: Mock,
    config: dict[str, str],
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
) -> None:
    """Test that old integer-based device identifiers are migrated to strings."""
    old_identifiers = {(DOMAIN, 12345)}

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=old_identifiers,
        manufacturer="SimpliSafe",
        name="old",
    )

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, 12345), config_entry.entry_id
        )
        is None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "12345"), config_entry.entry_id
        )
        is not None
    )


async def test_base_station_model_is_string(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
) -> None:
    """Test that the base station model is stored as a string in the device registry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12345"), config_entry.entry_id
    )
    assert device is not None
    assert isinstance(device.model, str)


async def test_glass_break_device_class(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    patch_simplisafe_api: None,
    system_v3: SystemV3,
) -> None:
    """Test the glass break binary sensor device class."""
    system_v3.sensor_data = copy.deepcopy(system_v3.sensor_data)
    system_v3.sensor_data["glass"] = {
        "serial": "glass",
        "type": 6,
        "name": "Living Room",
        "status": {"triggered": False},
        "flags": {"lowBattery": False, "offline": False},
    }
    system_v3.generate_device_objects()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, "glass"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.GLASS_BREAK


async def test_coordinator_update_triggers_reauth_on_invalid_credentials(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    system_v3,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that InvalidCredentialsError triggers a reauth flow."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    system_v3.async_update = AsyncMock(side_effect=InvalidCredentialsError("fail"))

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    flow = flows[0]
    assert flow.get("context", {}).get("source") == SOURCE_REAUTH
    assert flow.get("context", {}).get("entry_id") == config_entry.entry_id


@pytest.mark.parametrize(
    "exc",
    [RequestError, EndpointUnavailableError, SimplipyError],
)
async def test_coordinator_update_failure_keeps_entity_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    system_v3,
    freezer: FrozenDateTimeFactory,
    exc: type[SimplipyError],
) -> None:
    """Test single coordinator failure doesn't mark entities unavailable."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("lock.front_door_lock").state != STATE_UNAVAILABLE

    system_v3.async_update = AsyncMock(side_effect=exc("fail"))

    # Trigger one coordinator failure: error_count goes from 0 to 1, below threshold.
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("lock.front_door_lock").state != STATE_UNAVAILABLE


async def test_camera_device_registration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
) -> None:
    """Test that camera devices are registered in the device registry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1234567890"), config_entry.entry_id
    )
    assert camera_device is not None
    assert camera_device.manufacturer == "SimpliSafe"
    assert camera_device.model == "Camera"
    assert camera_device.name == "Camera Camera"

    # Verify via_device points to the base station:
    base_station = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12345"), config_entry.entry_id
    )
    assert base_station is not None
    assert camera_device.via_device_id == base_station.id


async def test_websocket_event_updates_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """Test that a push update from the websocket changes entity state."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Retrieve the event callback that was registered with the mock websocket.
    assert websocket.add_event_callback.called
    event_callback = websocket.add_event_callback.call_args[0][0]

    assert hass.states.get("lock.front_door_lock").state == "locked"

    # Fire an "unlock" websocket event for the test lock
    # (system_id=12345, serial="987").
    # CID 9700 maps to EVENT_LOCK_UNLOCKED in simplipy event mapping.
    event_callback(
        WebsocketEvent(
            event_cid=9700,
            info="Lock unlocked",
            system_id=12345,
            _raw_timestamp=0,
            _video=None,
            _vid=None,
            sensor_serial="987",
        )
    )
    await hass.async_block_till_done()

    assert hass.states.get("lock.front_door_lock").state == "unlocked"


async def test_websocket_retry_delay_resets_after_successful_listen(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test websocket retries restart at the initial delay after a successful listen."""
    patch_simplisafe_api.stop()
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.simplisafe")

    websocket.async_connect.side_effect = [
        WebsocketError("first failure"),
        None,
        WebsocketError("second failure"),
        WebsocketError("third failure"),
        WebsocketError("fourth failure"),
    ]
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    for delay in (
        WEBSOCKET_RETRY_DELAY,
        WEBSOCKET_RETRY_DELAY,
        WEBSOCKET_RETRY_DELAY * 2,
        WEBSOCKET_RETRY_DELAY * 4,
    ):
        freezer.tick(delay)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert [
        message for message in caplog.messages if message.startswith("Websocket error")
    ] == [
        f"Websocket error (1/3): first failure; retrying in {WEBSOCKET_RETRY_DELAY} seconds",
        f"Websocket error (1/3): second failure; retrying in {WEBSOCKET_RETRY_DELAY} seconds",
        f"Websocket error (2/3): third failure; retrying in {WEBSOCKET_RETRY_DELAY * 2} seconds",
        f"Websocket error (3/3): fourth failure; retrying in {WEBSOCKET_RETRY_DELAY * 4} seconds",
    ]
    assert (
        "Websocket connection failed, task exiting (3/3): fourth failure"
        in caplog.messages
    )


async def test_websocket_listener_failures_are_capped(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test repeated websocket listener failures stop after three attempts."""
    patch_simplisafe_api.stop()
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.simplisafe")

    websocket.async_listen.side_effect = WebsocketError("listener failure")
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    for delay in (
        WEBSOCKET_RETRY_DELAY,
        WEBSOCKET_RETRY_DELAY * 2,
        WEBSOCKET_RETRY_DELAY * 4,
    ):
        freezer.tick(delay)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert websocket.async_connect.await_count == 3
    assert (
        "Websocket connection failed, task exiting (3/3): listener failure"
        in caplog.messages
    )


async def test_websocket_start_and_restart_are_logged(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test initial websocket starts and restarts are logged distinctly."""
    patch_simplisafe_api.stop()

    async def stop_listening() -> None:
        raise asyncio.CancelledError

    websocket.async_listen.side_effect = stop_listening
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.simplisafe")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Starting websocket loop task" in caplog.messages
    assert "Restarting websocket loop task" in caplog.messages
