"""Test the Remootio cover entity."""
import logging
from typing import List
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

from aioremootio import (
    Event,
    EventSource,
    EventType,
    Listener,
    RemootioClient,
    State,
    StateChange,
)

from homeassistant.components.cover import DEVICE_CLASS_GARAGE, DOMAIN as COVER_DOMAIN
from homeassistant.components.remootio.const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HOST,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_capture_events

TDV_HOST = "127.0.0.1"
TDV_CREDENTIAL = "123456789A123456789B123456789C123456789D123456789E123456789FVXYZ"
TDV_SERIAL_NUMBER = "1234567890"
TDV_TITLE = "remootio"
TDV_ENTITY_ID = f"cover.{TDV_TITLE}"

_LOGGER = logging.getLogger(__name__)

remootio_client_state_change_listeners: List[Listener[StateChange]] = []
remootio_client_event_listeners: List[Listener[Event]] = []
remootio_client: Mock = None


@patch("homeassistant.components.remootio.create_client")
async def test_open_when_closed(remootio_create_client: Mock, hass: HomeAssistant):
    """Tests the opening of the Remootio controlled device."""
    global remootio_client

    remootio_client = _initialize_remootio_client()
    type(remootio_client).state = PropertyMock(return_value=State.CLOSED)

    remootio_create_client.return_value = remootio_client

    state_changed_events = async_capture_events(hass, "state_changed")

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TDV_HOST,
            CONF_API_SECRET_KEY: TDV_CREDENTIAL,
            CONF_API_AUTH_KEY: TDV_CREDENTIAL,
            CONF_DEVICE_CLASS: DEVICE_CLASS_GARAGE,
            CONF_SERIAL_NUMBER: TDV_SERIAL_NUMBER,
        },
        unique_id=TDV_SERIAL_NUMBER,
        title=TDV_TITLE,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(TDV_ENTITY_ID).state == STATE_CLOSED

    await hass.services.async_call(
        COVER_DOMAIN,
        "open_cover",
        service_data={"entity_id": TDV_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert hass.states.get(TDV_ENTITY_ID).state == STATE_OPEN

    assert len(state_changed_events) == 3
    _assert_state_changed_event(state_changed_events[0], None, STATE_CLOSED)
    _assert_state_changed_event(state_changed_events[1], STATE_CLOSED, STATE_OPENING)
    _assert_state_changed_event(state_changed_events[2], STATE_OPENING, STATE_OPEN)


@patch("homeassistant.components.remootio.create_client")
async def test_open_when_open(remootio_create_client: Mock, hass: HomeAssistant):
    """Tests the opening of the Remootio controlled device when it is open. In this case no state change should be occur."""
    global remootio_client

    remootio_client = _initialize_remootio_client()
    type(remootio_client).state = PropertyMock(return_value=State.OPEN)

    remootio_create_client.return_value = remootio_client

    state_changed_events = async_capture_events(hass, "state_changed")

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TDV_HOST,
            CONF_API_SECRET_KEY: TDV_CREDENTIAL,
            CONF_API_AUTH_KEY: TDV_CREDENTIAL,
            CONF_DEVICE_CLASS: DEVICE_CLASS_GARAGE,
            CONF_SERIAL_NUMBER: TDV_SERIAL_NUMBER,
        },
        unique_id=TDV_SERIAL_NUMBER,
        title=TDV_TITLE,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(TDV_ENTITY_ID).state == STATE_OPEN

    await hass.services.async_call(
        COVER_DOMAIN,
        "open_cover",
        service_data={"entity_id": TDV_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert hass.states.get(TDV_ENTITY_ID).state == STATE_OPEN

    assert len(state_changed_events) == 1
    _assert_state_changed_event(state_changed_events[0], None, STATE_OPEN)


@patch("homeassistant.components.remootio.create_client")
async def test_close_when_open(remootio_create_client: Mock, hass: HomeAssistant):
    """Tests the closing of the Remootio controlled device."""
    global remootio_client

    remootio_client = _initialize_remootio_client()
    type(remootio_client).state = PropertyMock(return_value=State.OPEN)

    remootio_create_client.return_value = remootio_client

    state_changed_events = async_capture_events(hass, "state_changed")

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TDV_HOST,
            CONF_API_SECRET_KEY: TDV_CREDENTIAL,
            CONF_API_AUTH_KEY: TDV_CREDENTIAL,
            CONF_DEVICE_CLASS: DEVICE_CLASS_GARAGE,
            CONF_SERIAL_NUMBER: TDV_SERIAL_NUMBER,
        },
        unique_id=TDV_SERIAL_NUMBER,
        title=TDV_TITLE,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(TDV_ENTITY_ID).state == STATE_OPEN

    await hass.services.async_call(
        COVER_DOMAIN,
        "close_cover",
        service_data={"entity_id": TDV_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert hass.states.get(TDV_ENTITY_ID).state == STATE_CLOSED

    assert len(state_changed_events) == 3
    _assert_state_changed_event(state_changed_events[0], None, STATE_OPEN)
    _assert_state_changed_event(state_changed_events[1], STATE_OPEN, STATE_CLOSING)
    _assert_state_changed_event(state_changed_events[2], STATE_CLOSING, STATE_CLOSED)


@patch("homeassistant.components.remootio.create_client")
async def test_close_when_closed(remootio_create_client: Mock, hass: HomeAssistant):
    """Tests the closing the Remootio controlled device when it is closed. In this case no state change should be occur."""
    global remootio_client

    remootio_client = _initialize_remootio_client()
    type(remootio_client).state = PropertyMock(return_value=State.CLOSED)

    remootio_create_client.return_value = remootio_client

    state_changed_events = async_capture_events(hass, "state_changed")

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TDV_HOST,
            CONF_API_SECRET_KEY: TDV_CREDENTIAL,
            CONF_API_AUTH_KEY: TDV_CREDENTIAL,
            CONF_DEVICE_CLASS: DEVICE_CLASS_GARAGE,
            CONF_SERIAL_NUMBER: TDV_SERIAL_NUMBER,
        },
        unique_id=TDV_SERIAL_NUMBER,
        title=TDV_TITLE,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(TDV_ENTITY_ID).state == STATE_CLOSED

    await hass.services.async_call(
        COVER_DOMAIN,
        "close_cover",
        service_data={"entity_id": TDV_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert hass.states.get(TDV_ENTITY_ID).state == STATE_CLOSED

    assert len(state_changed_events) == 1
    _assert_state_changed_event(state_changed_events[0], None, STATE_CLOSED)


@patch("homeassistant.components.remootio.create_client")
async def test_event_left_open(remootio_create_client: Mock, hass: HomeAssistant):
    """Tests the handling of the LEFT_OPEN event fired by Remootio if the controlled device has been left open."""
    global remootio_client

    remootio_client = _initialize_remootio_client()
    type(remootio_client).state = PropertyMock(return_value=State.OPEN)

    remootio_create_client.return_value = remootio_client

    left_open_events = async_capture_events(hass, "remootio_left_open")

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TDV_HOST,
            CONF_API_SECRET_KEY: TDV_CREDENTIAL,
            CONF_API_AUTH_KEY: TDV_CREDENTIAL,
            CONF_DEVICE_CLASS: DEVICE_CLASS_GARAGE,
            CONF_SERIAL_NUMBER: TDV_SERIAL_NUMBER,
        },
        unique_id=TDV_SERIAL_NUMBER,
        title=TDV_TITLE,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(TDV_ENTITY_ID).state == STATE_OPEN

    await _remootio_client_trigger_event(
        Event(EventSource.WIFI, EventType.LEFT_OPEN, None)
    )
    await hass.async_block_till_done()

    assert len(left_open_events) == 1
    assert left_open_events[0].data["entity_id"] == TDV_ENTITY_ID


def _assert_state_changed_event(
    state_changed_event, expected_old_state, expected_new_state
):
    assert state_changed_event.data["entity_id"] == TDV_ENTITY_ID
    assert (
        state_changed_event.data["old_state"].state == expected_old_state
        if expected_old_state is not None
        else state_changed_event.data["old_state"] is None
    )
    assert (
        state_changed_event.data["new_state"].state == expected_new_state
        if expected_new_state is not None
        else state_changed_event.data["new_state"] is None
    )


async def _remootio_client_invoke_state_change_listeners(state_change: StateChange):
    global remootio_client_state_change_listeners, remootio_client

    if len(remootio_client_state_change_listeners) > 0:
        for (
            remootio_client_state_change_listener
        ) in remootio_client_state_change_listeners:
            _LOGGER.debug(
                f"Invoking state change listener {type(remootio_client_state_change_listener)}..."
            )
            await remootio_client_state_change_listener.execute(
                remootio_client, state_change
            )


async def _remootio_client_invoke_event_listeners(event: Event):
    global remootio_client_event_listeners, remootio_client

    if len(remootio_client_event_listeners) > 0:
        for remootio_client_event_listener in remootio_client_event_listeners:
            _LOGGER.debug(
                f"Invoking event listener {type(remootio_client_event_listener)}..."
            )
            await remootio_client_event_listener.execute(remootio_client, event)


async def _remootio_client_change_state(new_state: State):
    global remootio_client

    old_state: State = remootio_client.state

    do_change_state: bool = False
    if old_state == new_state:
        pass
    elif old_state == State.NO_SENSOR_INSTALLED:
        do_change_state = new_state != State.NO_SENSOR_INSTALLED
    elif old_state == State.UNKNOWN:
        do_change_state = new_state != State.UNKNOWN
    elif old_state == State.CLOSED:
        do_change_state = (
            (new_state == State.UNKNOWN)
            or (new_state == State.NO_SENSOR_INSTALLED)
            or (new_state == State.OPENING)
            or (new_state == State.OPEN)
        )

        if new_state == State.CLOSING:
            await _remootio_client_change_state(State.UNKNOWN)
            old_state = remootio_client.state
            do_change_state = True
    elif old_state == State.OPEN:
        do_change_state = (
            (new_state == State.UNKNOWN)
            or (new_state == State.NO_SENSOR_INSTALLED)
            or (new_state == State.CLOSING)
            or (new_state == State.CLOSED)
        )

        if new_state == State.OPENING:
            await _remootio_client_change_state(State.UNKNOWN)
            old_state = remootio_client.state
            do_change_state = True
    elif old_state == State.CLOSING:
        do_change_state = (
            (new_state == State.UNKNOWN)
            or (new_state == State.NO_SENSOR_INSTALLED)
            or (new_state == State.CLOSED)
        )

        if new_state == State.OPENING:
            await _remootio_client_change_state(State.UNKNOWN)
            old_state = remootio_client.state
            do_change_state = True
        elif new_state == State.OPEN:
            await _remootio_client_change_state(State.UNKNOWN)
            old_state = remootio_client.state
            do_change_state = True
    elif old_state == State.OPENING:
        do_change_state = (
            (new_state == State.UNKNOWN)
            or (new_state == State.NO_SENSOR_INSTALLED)
            or (new_state == State.OPEN)
        )

        if new_state == State.CLOSING:
            await _remootio_client_change_state(State.UNKNOWN)
            old_state = remootio_client.state
            do_change_state = True
        elif new_state == State.CLOSED:
            await _remootio_client_change_state(State.UNKNOWN)
            old_state = remootio_client.state
            do_change_state = True

    if do_change_state:
        type(remootio_client).state = PropertyMock(return_value=new_state)

        await _remootio_client_invoke_state_change_listeners(
            StateChange(old_state, new_state)
        )


async def _remootio_client_trigger_event(event: Event):
    await _remootio_client_invoke_event_listeners(event)


def _initialize_remootio_client() -> Mock:
    async def add_state_change_listener(state_change_listener: Listener[StateChange]):
        _LOGGER.debug("add_state_change_listener invoked.")
        global remootio_client_state_change_listeners
        remootio_client_state_change_listeners.append(state_change_listener)

    async def add_event_listener(event_listener: Listener[Event]):
        _LOGGER.debug("add_event_listener invoked.")
        global remootio_client_event_listeners
        remootio_client_event_listeners.append(event_listener)

    async def trigger_state_update():
        _LOGGER.debug("trigger_state_update invoked.")
        pass

    async def trigger_open():
        _LOGGER.debug("trigger_open invoked.")
        global remootio_client

        if remootio_client.state == State.CLOSED:
            await _remootio_client_change_state(State.OPENING)

        await _remootio_client_change_state(State.OPEN)

    async def trigger_close():
        _LOGGER.debug("trigger_close invoked.")

        if remootio_client.state == State.OPEN:
            await _remootio_client_change_state(State.CLOSING)

        await _remootio_client_change_state(State.CLOSED)

    global remootio_client_state_change_listeners, remootio_client_event_listeners

    remootio_client_state_change_listeners = []
    remootio_client_event_listeners = []

    result: Mock = MagicMock(RemootioClient)
    type(result).state = PropertyMock(return_value=State.UNKNOWN)
    result.trigger_state_update = AsyncMock(side_effect=trigger_state_update)
    result.trigger_open = AsyncMock(side_effect=trigger_open)
    result.trigger_close = AsyncMock(side_effect=trigger_close)
    result.add_state_change_listener = AsyncMock(side_effect=add_state_change_listener)
    result.add_event_listener = AsyncMock(side_effect=add_event_listener)

    return result
