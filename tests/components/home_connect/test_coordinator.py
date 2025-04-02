"""Test for Home Connect coordinator."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfHomeAppliances,
    ArrayOfSettings,
    ArrayOfStatus,
    Event,
    EventKey,
    EventMessage,
    EventType,
    HomeAppliance,
)
from aiohomeconnect.model.error import (
    EventStreamInterruptedError,
    HomeConnectApiError,
    HomeConnectError,
    HomeConnectRequestError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.home_connect.const import (
    BSH_DOOR_STATE_OPEN,
    BSH_EVENT_PRESENT_STATE_PRESENT,
    BSH_POWER_OFF,
    DOMAIN,
)
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.config_entries import ConfigEntries, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_STATE_REPORTED,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import (
    Event as HassEvent,
    EventStateReportedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR, Platform.SWITCH]


async def test_coordinator_update(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED


async def test_coordinator_update_failing_get_appliances(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test that the coordinator raises ConfigEntryNotReady when it fails to get appliances."""
    client_with_exception.get_home_appliances.return_value = None
    client_with_exception.get_home_appliances.side_effect = HomeConnectError()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client_with_exception)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize("platforms", [("binary_sensor",)])
@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_coordinator_failure_refresh_and_stream(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
    appliance: HomeAppliance,
) -> None:
    """Test entity available state via coordinator refresh and event stream."""
    appliance_data = (
        cast(str, appliance.to_json())
        .replace("ha_id", "haId")
        .replace("e_number", "enumber")
    )
    entity_id_1 = "binary_sensor.washer_remote_control"
    entity_id_2 = "binary_sensor.washer_remote_start"
    await async_setup_component(hass, HA_DOMAIN, {})
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    state = hass.states.get(entity_id_1)
    assert state
    assert state.state != STATE_UNAVAILABLE
    state = hass.states.get(entity_id_2)
    assert state
    assert state.state != STATE_UNAVAILABLE

    client.get_home_appliances.side_effect = HomeConnectError()

    # Force a coordinator refresh.
    await hass.services.async_call(
        HA_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id_1}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id_1)
    assert state
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get(entity_id_2)
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Test that the entity becomes available again after a successful update.

    client.get_home_appliances.side_effect = None
    client.get_home_appliances.return_value = ArrayOfHomeAppliances(
        [HomeAppliance.from_json(appliance_data)]
    )

    # Move time forward to pass the debounce time.
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Force a coordinator refresh.
    await hass.services.async_call(
        HA_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id_1}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id_1)
    assert state
    assert state.state != STATE_UNAVAILABLE
    state = hass.states.get(entity_id_2)
    assert state
    assert state.state != STATE_UNAVAILABLE

    # Test that the event stream makes the entity go available too.

    # First make the entity unavailable.
    client.get_home_appliances.side_effect = HomeConnectError()

    # Move time forward to pass the debounce time
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Force a coordinator refresh
    await hass.services.async_call(
        HA_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id_1}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id_1)
    assert state
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get(entity_id_2)
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Now make the entity available again.
    client.get_home_appliances.side_effect = None
    client.get_home_appliances.return_value = ArrayOfHomeAppliances(
        [HomeAppliance.from_json(appliance_data)]
    )

    # One event should make all entities for this appliance available again.
    event_message = EventMessage(
        appliance.ha_id,
        EventType.STATUS,
        ArrayOfEvents(
            [
                Event(
                    key=EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
                    raw_key=EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE.value,
                    timestamp=0,
                    level="",
                    handling="",
                    value=False,
                )
            ],
        ),
    )
    await client.add_events([event_message])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id_1)
    assert state
    assert state.state != STATE_UNAVAILABLE
    state = hass.states.get(entity_id_2)
    assert state
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "mock_method",
    [
        "get_settings",
        "get_status",
        "get_all_programs",
        "get_available_commands",
        "get_available_program",
    ],
)
async def test_coordinator_update_failing(
    mock_method: str,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test that although is not possible to get settings and status, the config entry is loaded.

    This is for cases where some appliances are reachable and some are not in the same configuration entry.
    """
    setattr(client, mock_method, AsyncMock(side_effect=HomeConnectError()))

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    getattr(client, mock_method).assert_called()


@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
@pytest.mark.parametrize(
    ("event_type", "event_key", "event_value", ATTR_ENTITY_ID),
    [
        (
            EventType.STATUS,
            EventKey.BSH_COMMON_STATUS_DOOR_STATE,
            BSH_DOOR_STATE_OPEN,
            "sensor.dishwasher_door",
        ),
        (
            EventType.NOTIFY,
            EventKey.BSH_COMMON_SETTING_POWER_STATE,
            BSH_POWER_OFF,
            "switch.dishwasher_power",
        ),
        (
            EventType.EVENT,
            EventKey.DISHCARE_DISHWASHER_EVENT_SALT_NEARLY_EMPTY,
            BSH_EVENT_PRESENT_STATE_PRESENT,
            "sensor.dishwasher_salt_nearly_empty",
        ),
    ],
)
async def test_event_listener(
    event_type: EventType,
    event_key: EventKey,
    event_value: str,
    entity_id: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance: HomeAppliance,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the event listener works."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    state = hass.states.get(entity_id)

    event_message = EventMessage(
        appliance.ha_id,
        event_type,
        ArrayOfEvents(
            [
                Event(
                    key=event_key,
                    raw_key=event_key.value,
                    timestamp=0,
                    level="",
                    handling="",
                    value=event_value,
                )
            ],
        ),
    )
    await client.add_events([event_message])
    await hass.async_block_till_done()

    new_state = hass.states.get(entity_id)
    assert new_state
    if state is not None:
        assert new_state.state != state.state

    # Following, we are gonna check that the listeners are clean up correctly
    new_entity_id = entity_id + "_new"
    listener = MagicMock()

    @callback
    def listener_callback(event: HassEvent[EventStateReportedData]) -> None:
        listener(event.data["entity_id"])

    @callback
    def event_filter(_: EventStateReportedData) -> bool:
        return True

    hass.bus.async_listen(EVENT_STATE_REPORTED, listener_callback, event_filter)

    entity_registry.async_update_entity(entity_id, new_entity_id=new_entity_id)
    await hass.async_block_till_done()
    await client.add_events([event_message])
    await hass.async_block_till_done()

    # Because the entity's id has been updated, the entity has been unloaded
    # and the listener has been removed, and the new entity adds a new listener,
    # so the only entity that should report states is the one with the new entity id
    listener.assert_called_once_with(new_entity_id)


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def tests_receive_setting_and_status_for_first_time_at_events(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance: HomeAppliance,
) -> None:
    """Test that the event listener is capable of receiving settings and status for the first time."""
    client.get_setting = AsyncMock(return_value=ArrayOfSettings([]))
    client.get_status = AsyncMock(return_value=ArrayOfStatus([]))

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.NOTIFY,
                ArrayOfEvents(
                    [
                        Event(
                            key=EventKey.LAUNDRY_CARE_WASHER_SETTING_I_DOS_1_BASE_LEVEL,
                            raw_key=EventKey.LAUNDRY_CARE_WASHER_SETTING_I_DOS_1_BASE_LEVEL.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value="some value",
                        )
                    ],
                ),
            ),
            EventMessage(
                appliance.ha_id,
                EventType.STATUS,
                ArrayOfEvents(
                    [
                        Event(
                            key=EventKey.BSH_COMMON_STATUS_DOOR_STATE,
                            raw_key=EventKey.BSH_COMMON_STATUS_DOOR_STATE.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value="some value",
                        )
                    ],
                ),
            ),
        ]
    )
    await hass.async_block_till_done()
    assert len(config_entry._background_tasks) == 1
    assert config_entry.state == ConfigEntryState.LOADED


async def test_event_listener_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client_with_exception: MagicMock,
) -> None:
    """Test that the configuration entry is reloaded when the event stream raises an API error."""
    client_with_exception.stream_all_events = MagicMock(
        side_effect=HomeConnectApiError("error.key", "error description")
    )

    with patch.object(
        ConfigEntries,
        "async_schedule_reload",
    ) as mock_schedule_reload:
        await integration_setup(client_with_exception)
        await hass.async_block_till_done()

    client_with_exception.stream_all_events.assert_called_once()
    mock_schedule_reload.assert_called_once_with(config_entry.entry_id)
    assert not config_entry._background_tasks


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize("platforms", [("sensor",)])
@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
@pytest.mark.parametrize(
    "exception",
    [HomeConnectRequestError(), EventStreamInterruptedError()],
)
@pytest.mark.parametrize(
    (
        "entity_id",
        "initial_state",
        "event_key",
        "event_value",
        "after_event_expected_state",
    ),
    [
        (
            "sensor.washer_door",
            "closed",
            EventKey.BSH_COMMON_STATUS_DOOR_STATE,
            BSH_DOOR_STATE_OPEN,
            "open",
        ),
    ],
)
async def test_event_listener_resilience(
    entity_id: str,
    initial_state: str,
    event_key: EventKey,
    event_value: Any,
    after_event_expected_state: str,
    exception: HomeConnectError,
    hass: HomeAssistant,
    appliance: HomeAppliance,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that the event listener is resilient to interruptions."""
    future = hass.loop.create_future()

    async def stream_exception():
        yield await future

    client.stream_all_events = MagicMock(
        side_effect=[stream_exception(), client.stream_all_events()]
    )

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(config_entry._background_tasks) == 1

    state = hass.states.get(entity_id)
    assert state
    assert state.state == initial_state

    future.set_exception(exception)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert client.stream_all_events.call_count == 2

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.STATUS,
                ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=event_value,
                        )
                    ],
                ),
            ),
        ]
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == after_event_expected_state


async def test_devices_updated_on_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test handling of devices added or deleted while event stream is down."""
    appliances: list[HomeAppliance] = (
        client.get_home_appliances.return_value.homeappliances
    )
    assert len(appliances) >= 3
    client.get_home_appliances = AsyncMock(
        return_value=ArrayOfHomeAppliances(appliances[:2]),
    )

    await async_setup_component(hass, HA_DOMAIN, {})
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    for appliance in appliances[:2]:
        assert device_registry.async_get_device({(DOMAIN, appliance.ha_id)})
    assert not device_registry.async_get_device({(DOMAIN, appliances[2].ha_id)})

    client.get_home_appliances = AsyncMock(
        return_value=ArrayOfHomeAppliances(appliances[1:3]),
    )
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "switch.dishwasher_power"},
        blocking=True,
    )

    assert not device_registry.async_get_device({(DOMAIN, appliances[0].ha_id)})
    for appliance in appliances[2:3]:
        assert device_registry.async_get_device({(DOMAIN, appliance.ha_id)})
