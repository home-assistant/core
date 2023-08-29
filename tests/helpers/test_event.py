"""Test event helpers."""

import asyncio
from collections.abc import Callable
import contextlib
from datetime import date, datetime, timedelta
from unittest.mock import patch

from astral import LocationInfo
import astral.sun
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import jinja2
import pytest

from homeassistant.const import MATCH_ALL
import homeassistant.core as ha
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.helpers.event import (
    EventStateChangedData,
    TrackStates,
    TrackTemplate,
    TrackTemplateResult,
    async_call_later,
    async_track_device_registry_updated_event,
    async_track_entity_registry_updated_event,
    async_track_point_in_time,
    async_track_point_in_utc_time,
    async_track_same_state,
    async_track_state_added_domain,
    async_track_state_change,
    async_track_state_change_event,
    async_track_state_change_filtered,
    async_track_state_removed_domain,
    async_track_sunrise,
    async_track_sunset,
    async_track_template,
    async_track_template_result,
    async_track_time_change,
    async_track_time_interval,
    async_track_utc_time_change,
    track_point_in_utc_time,
)
from homeassistant.helpers.template import Template, result_as_boolean
from homeassistant.helpers.typing import EventType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_fire_time_changed_exact

DEFAULT_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE


async def test_track_point_in_time(hass: HomeAssistant) -> None:
    """Test track point in time."""
    before_birthday = datetime(1985, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)
    birthday_paulus = datetime(1986, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)
    after_birthday = datetime(1987, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)

    runs = []

    async_track_point_in_utc_time(
        hass, callback(lambda x: runs.append(x)), birthday_paulus
    )

    async_fire_time_changed(hass, before_birthday)
    await hass.async_block_till_done()
    assert len(runs) == 0

    async_fire_time_changed(hass, birthday_paulus)
    await hass.async_block_till_done()
    assert len(runs) == 1

    # A point in time tracker will only fire once, this should do nothing
    async_fire_time_changed(hass, birthday_paulus)
    await hass.async_block_till_done()
    assert len(runs) == 1

    async_track_point_in_utc_time(
        hass, callback(lambda x: runs.append(x)), birthday_paulus
    )

    async_fire_time_changed(hass, after_birthday)
    await hass.async_block_till_done()
    assert len(runs) == 2

    unsub = async_track_point_in_time(
        hass, callback(lambda x: runs.append(x)), birthday_paulus
    )
    unsub()

    async_fire_time_changed(hass, after_birthday)
    await hass.async_block_till_done()
    assert len(runs) == 2


async def test_track_point_in_time_drift_rearm(hass: HomeAssistant) -> None:
    """Test tasks with the time rolling backwards."""
    specific_runs = []

    now = dt_util.utcnow()

    time_that_will_not_match_right_away = datetime(
        now.year + 1, 5, 24, 21, 59, 55, tzinfo=dt_util.UTC
    )

    async_track_point_in_utc_time(
        hass,
        callback(lambda x: specific_runs.append(x)),
        time_that_will_not_match_right_away,
    )

    async_fire_time_changed(
        hass,
        datetime(now.year + 1, 5, 24, 21, 59, 00, tzinfo=dt_util.UTC),
        fire_all=True,
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    async_fire_time_changed(
        hass,
        datetime(now.year + 1, 5, 24, 21, 59, 55, tzinfo=dt_util.UTC),
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1


async def test_track_state_change_from_to_state_match(hass: HomeAssistant) -> None:
    """Test track_state_change with from and to state matchers."""
    from_and_to_state_runs = []
    only_from_runs = []
    only_to_runs = []
    match_all_runs = []
    no_to_from_specified_runs = []

    def from_and_to_state_callback(entity_id, old_state, new_state):
        from_and_to_state_runs.append(1)

    def only_from_state_callback(entity_id, old_state, new_state):
        only_from_runs.append(1)

    def only_to_state_callback(entity_id, old_state, new_state):
        only_to_runs.append(1)

    def match_all_callback(entity_id, old_state, new_state):
        match_all_runs.append(1)

    def no_to_from_specified_callback(entity_id, old_state, new_state):
        no_to_from_specified_runs.append(1)

    async_track_state_change(
        hass, "light.Bowl", from_and_to_state_callback, "on", "off"
    )
    async_track_state_change(hass, "light.Bowl", only_from_state_callback, "on", None)
    async_track_state_change(
        hass, "light.Bowl", only_to_state_callback, None, ["off", "standby"]
    )
    async_track_state_change(
        hass, "light.Bowl", match_all_callback, MATCH_ALL, MATCH_ALL
    )
    async_track_state_change(hass, "light.Bowl", no_to_from_specified_callback)

    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(from_and_to_state_runs) == 0
    assert len(only_from_runs) == 0
    assert len(only_to_runs) == 0
    assert len(match_all_runs) == 1
    assert len(no_to_from_specified_runs) == 1

    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(from_and_to_state_runs) == 1
    assert len(only_from_runs) == 1
    assert len(only_to_runs) == 1
    assert len(match_all_runs) == 2
    assert len(no_to_from_specified_runs) == 2

    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(from_and_to_state_runs) == 1
    assert len(only_from_runs) == 1
    assert len(only_to_runs) == 1
    assert len(match_all_runs) == 3
    assert len(no_to_from_specified_runs) == 3

    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(from_and_to_state_runs) == 1
    assert len(only_from_runs) == 1
    assert len(only_to_runs) == 1
    assert len(match_all_runs) == 3
    assert len(no_to_from_specified_runs) == 3

    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(from_and_to_state_runs) == 2
    assert len(only_from_runs) == 2
    assert len(only_to_runs) == 2
    assert len(match_all_runs) == 4
    assert len(no_to_from_specified_runs) == 4

    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(from_and_to_state_runs) == 2
    assert len(only_from_runs) == 2
    assert len(only_to_runs) == 2
    assert len(match_all_runs) == 4
    assert len(no_to_from_specified_runs) == 4


async def test_track_state_change(hass: HomeAssistant) -> None:
    """Test track_state_change."""
    # 2 lists to track how often our callbacks get called
    specific_runs = []
    wildcard_runs = []
    wildercard_runs = []

    def specific_run_callback(entity_id, old_state, new_state):
        specific_runs.append(1)

    # This is the rare use case
    async_track_state_change(hass, "light.Bowl", specific_run_callback, "on", "off")

    @ha.callback
    def wildcard_run_callback(entity_id, old_state, new_state):
        wildcard_runs.append((old_state, new_state))

    # This is the most common use case
    async_track_state_change(hass, "light.Bowl", wildcard_run_callback)

    async def wildercard_run_callback(entity_id, old_state, new_state):
        wildercard_runs.append((old_state, new_state))

    async_track_state_change(hass, MATCH_ALL, wildercard_run_callback)

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 0
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1
    assert wildcard_runs[-1][0] is None
    assert wildcard_runs[-1][1] is not None

    # Set same state should not trigger a state change/listener
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 0
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    # State change off -> on
    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 2
    assert len(wildercard_runs) == 2

    # State change off -> off
    hass.states.async_set("light.Bowl", "off", {"some_attr": 1})
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 3
    assert len(wildercard_runs) == 3

    # State change off -> on
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 4
    assert len(wildercard_runs) == 4

    hass.states.async_remove("light.bowl")
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 5
    assert len(wildercard_runs) == 5
    assert wildcard_runs[-1][0] is not None
    assert wildcard_runs[-1][1] is None
    assert wildercard_runs[-1][0] is not None
    assert wildercard_runs[-1][1] is None

    # Set state for different entity id
    hass.states.async_set("switch.kitchen", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 5
    assert len(wildercard_runs) == 6


async def test_async_track_state_change_filtered(hass: HomeAssistant) -> None:
    """Test async_track_state_change_filtered."""
    single_entity_id_tracker = []
    multiple_entity_id_tracker = []

    @ha.callback
    def single_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        single_entity_id_tracker.append((old_state, new_state))

    @ha.callback
    def multiple_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        multiple_entity_id_tracker.append((old_state, new_state))

    @ha.callback
    def callback_that_throws(event: EventType[EventStateChangedData]) -> None:
        raise ValueError

    track_single = async_track_state_change_filtered(
        hass, TrackStates(False, {"light.bowl"}, None), single_run_callback
    )
    assert track_single.listeners == {
        "all": False,
        "domains": None,
        "entities": {"light.bowl"},
    }

    track_multi = async_track_state_change_filtered(
        hass, TrackStates(False, {"light.bowl"}, {"switch"}), multiple_run_callback
    )
    assert track_multi.listeners == {
        "all": False,
        "domains": {"switch"},
        "entities": {"light.bowl"},
    }

    track_throws = async_track_state_change_filtered(
        hass, TrackStates(False, {"light.bowl"}, {"switch"}), callback_that_throws
    )
    assert track_throws.listeners == {
        "all": False,
        "domains": {"switch"},
        "entities": {"light.bowl"},
    }

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert single_entity_id_tracker[-1][0] is None
    assert single_entity_id_tracker[-1][1] is not None
    assert len(multiple_entity_id_tracker) == 1
    assert multiple_entity_id_tracker[-1][0] is None
    assert multiple_entity_id_tracker[-1][1] is not None

    # Set same state should not trigger a state change/listener
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(multiple_entity_id_tracker) == 1

    # State change off -> on
    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 2
    assert len(multiple_entity_id_tracker) == 2

    # State change off -> off
    hass.states.async_set("light.Bowl", "off", {"some_attr": 1})
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 3
    assert len(multiple_entity_id_tracker) == 3

    # State change off -> on
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 4
    assert len(multiple_entity_id_tracker) == 4

    hass.states.async_remove("light.bowl")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 5
    assert single_entity_id_tracker[-1][0] is not None
    assert single_entity_id_tracker[-1][1] is None
    assert len(multiple_entity_id_tracker) == 5
    assert multiple_entity_id_tracker[-1][0] is not None
    assert multiple_entity_id_tracker[-1][1] is None

    # Set state for different entity id
    hass.states.async_set("switch.kitchen", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 5
    assert len(multiple_entity_id_tracker) == 6

    track_single.async_remove()
    # Ensure unsubing the listener works
    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 5
    assert len(multiple_entity_id_tracker) == 7

    assert track_multi.listeners == {
        "all": False,
        "domains": {"switch"},
        "entities": {"light.bowl"},
    }
    track_multi.async_update_listeners(TrackStates(False, {"light.bowl"}, None))
    assert track_multi.listeners == {
        "all": False,
        "domains": None,
        "entities": {"light.bowl"},
    }
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(multiple_entity_id_tracker) == 8
    hass.states.async_set("switch.kitchen", "off")
    await hass.async_block_till_done()
    assert len(multiple_entity_id_tracker) == 8

    track_multi.async_update_listeners(TrackStates(True, None, None))
    hass.states.async_set("switch.kitchen", "off")
    await hass.async_block_till_done()
    assert len(multiple_entity_id_tracker) == 8
    hass.states.async_set("switch.any", "off")
    await hass.async_block_till_done()
    assert len(multiple_entity_id_tracker) == 9

    track_multi.async_remove()
    track_throws.async_remove()


async def test_async_track_state_change_event(hass: HomeAssistant) -> None:
    """Test async_track_state_change_event."""
    single_entity_id_tracker = []
    multiple_entity_id_tracker = []

    @ha.callback
    def single_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        single_entity_id_tracker.append((old_state, new_state))

    @ha.callback
    def multiple_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        multiple_entity_id_tracker.append((old_state, new_state))

    @ha.callback
    def callback_that_throws(event: EventType[EventStateChangedData]) -> None:
        raise ValueError

    unsub_single = async_track_state_change_event(
        hass, ["light.Bowl"], single_run_callback
    )
    unsub_multi = async_track_state_change_event(
        hass, ["light.Bowl", "switch.kitchen"], multiple_run_callback
    )
    unsub_throws = async_track_state_change_event(
        hass, ["light.Bowl", "switch.kitchen"], callback_that_throws
    )

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert single_entity_id_tracker[-1][0] is None
    assert single_entity_id_tracker[-1][1] is not None
    assert len(multiple_entity_id_tracker) == 1
    assert multiple_entity_id_tracker[-1][0] is None
    assert multiple_entity_id_tracker[-1][1] is not None

    # Set same state should not trigger a state change/listener
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(multiple_entity_id_tracker) == 1

    # State change off -> on
    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 2
    assert len(multiple_entity_id_tracker) == 2

    # State change off -> off
    hass.states.async_set("light.Bowl", "off", {"some_attr": 1})
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 3
    assert len(multiple_entity_id_tracker) == 3

    # State change off -> on
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 4
    assert len(multiple_entity_id_tracker) == 4

    hass.states.async_remove("light.bowl")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 5
    assert single_entity_id_tracker[-1][0] is not None
    assert single_entity_id_tracker[-1][1] is None
    assert len(multiple_entity_id_tracker) == 5
    assert multiple_entity_id_tracker[-1][0] is not None
    assert multiple_entity_id_tracker[-1][1] is None

    # Set state for different entity id
    hass.states.async_set("switch.kitchen", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 5
    assert len(multiple_entity_id_tracker) == 6

    unsub_single()
    # Ensure unsubing the listener works
    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 5
    assert len(multiple_entity_id_tracker) == 7

    unsub_multi()
    unsub_throws()


async def test_async_track_state_change_event_with_empty_list(
    hass: HomeAssistant,
) -> None:
    """Test async_track_state_change_event passing an empty list of entities."""
    unsub_single = async_track_state_change_event(
        hass, [], ha.callback(lambda event: None)
    )
    unsub_single2 = async_track_state_change_event(
        hass, [], ha.callback(lambda event: None)
    )

    unsub_single2()
    unsub_single()


async def test_async_track_state_added_domain(hass: HomeAssistant) -> None:
    """Test async_track_state_added_domain."""
    single_entity_id_tracker = []
    multiple_entity_id_tracker = []

    @ha.callback
    def single_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        single_entity_id_tracker.append((old_state, new_state))

    @ha.callback
    def multiple_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        multiple_entity_id_tracker.append((old_state, new_state))

    @ha.callback
    def callback_that_throws(event):
        raise ValueError

    unsub_single = async_track_state_added_domain(hass, "light", single_run_callback)
    unsub_multi = async_track_state_added_domain(
        hass, ["light", "switch"], multiple_run_callback
    )
    unsub_throws = async_track_state_added_domain(
        hass, ["light", "switch"], callback_that_throws
    )

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert single_entity_id_tracker[-1][0] is None
    assert single_entity_id_tracker[-1][1] is not None
    assert len(multiple_entity_id_tracker) == 1
    assert multiple_entity_id_tracker[-1][0] is None
    assert multiple_entity_id_tracker[-1][1] is not None

    # Set same state should not trigger a state change/listener
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(multiple_entity_id_tracker) == 1

    # State change off -> on - nothing added so no trigger
    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(multiple_entity_id_tracker) == 1

    # State change off -> off - nothing added so no trigger
    hass.states.async_set("light.Bowl", "off", {"some_attr": 1})
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(multiple_entity_id_tracker) == 1

    # Removing state does not trigger
    hass.states.async_remove("light.bowl")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(multiple_entity_id_tracker) == 1

    # Set state for different entity id
    hass.states.async_set("switch.kitchen", "on")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(multiple_entity_id_tracker) == 2

    unsub_single()
    # Ensure unsubing the listener works
    hass.states.async_set("light.new", "off")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(multiple_entity_id_tracker) == 3

    unsub_multi()
    unsub_throws()


async def test_async_track_state_added_domain_with_empty_list(
    hass: HomeAssistant,
) -> None:
    """Test async_track_state_added_domain passing an empty list of domains."""
    unsub_single = async_track_state_added_domain(
        hass, [], ha.callback(lambda event: None)
    )
    unsub_single2 = async_track_state_added_domain(
        hass, [], ha.callback(lambda event: None)
    )

    unsub_single2()
    unsub_single()


async def test_async_track_state_removed_domain_with_empty_list(
    hass: HomeAssistant,
) -> None:
    """Test async_track_state_removed_domain passing an empty list of domains."""
    unsub_single = async_track_state_removed_domain(
        hass, [], ha.callback(lambda event: None)
    )
    unsub_single2 = async_track_state_removed_domain(
        hass, [], ha.callback(lambda event: None)
    )

    unsub_single2()
    unsub_single()


async def test_async_track_state_removed_domain(hass: HomeAssistant) -> None:
    """Test async_track_state_removed_domain."""
    single_entity_id_tracker = []
    multiple_entity_id_tracker = []

    @ha.callback
    def single_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        single_entity_id_tracker.append((old_state, new_state))

    @ha.callback
    def multiple_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        multiple_entity_id_tracker.append((old_state, new_state))

    @ha.callback
    def callback_that_throws(event):
        raise ValueError

    unsub_single = async_track_state_removed_domain(hass, "light", single_run_callback)
    unsub_multi = async_track_state_removed_domain(
        hass, ["light", "switch"], multiple_run_callback
    )
    unsub_throws = async_track_state_removed_domain(
        hass, ["light", "switch"], callback_that_throws
    )

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    hass.states.async_remove("light.Bowl")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert single_entity_id_tracker[-1][1] is None
    assert single_entity_id_tracker[-1][0] is not None
    assert len(multiple_entity_id_tracker) == 1
    assert multiple_entity_id_tracker[-1][1] is None
    assert multiple_entity_id_tracker[-1][0] is not None

    # Added and than removed (light)
    hass.states.async_set("light.Bowl", "on")
    hass.states.async_remove("light.Bowl")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 2
    assert len(multiple_entity_id_tracker) == 2

    # Added and than removed (light)
    hass.states.async_set("light.Bowl", "off")
    hass.states.async_remove("light.Bowl")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 3
    assert len(multiple_entity_id_tracker) == 3

    # Added and than removed (light)
    hass.states.async_set("light.Bowl", "off", {"some_attr": 1})
    hass.states.async_remove("light.Bowl")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 4
    assert len(multiple_entity_id_tracker) == 4

    # Added and than removed (switch)
    hass.states.async_set("switch.kitchen", "on")
    hass.states.async_remove("switch.kitchen")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 4
    assert len(multiple_entity_id_tracker) == 5

    unsub_single()
    # Ensure unsubing the listener works
    hass.states.async_set("light.new", "off")
    hass.states.async_remove("light.new")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 4
    assert len(multiple_entity_id_tracker) == 6

    unsub_multi()
    unsub_throws()


async def test_async_track_state_removed_domain_match_all(hass: HomeAssistant) -> None:
    """Test async_track_state_removed_domain with a match_all."""
    single_entity_id_tracker = []
    match_all_entity_id_tracker = []

    @ha.callback
    def single_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        single_entity_id_tracker.append((old_state, new_state))

    @ha.callback
    def match_all_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        match_all_entity_id_tracker.append((old_state, new_state))

    unsub_single = async_track_state_removed_domain(hass, "light", single_run_callback)
    unsub_match_all = async_track_state_removed_domain(
        hass, MATCH_ALL, match_all_run_callback
    )
    hass.states.async_set("light.new", "off")
    hass.states.async_remove("light.new")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(match_all_entity_id_tracker) == 1

    hass.states.async_set("switch.new", "off")
    hass.states.async_remove("switch.new")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(match_all_entity_id_tracker) == 2

    unsub_match_all()
    unsub_single()
    hass.states.async_set("switch.new", "off")
    hass.states.async_remove("switch.new")
    await hass.async_block_till_done()
    assert len(single_entity_id_tracker) == 1
    assert len(match_all_entity_id_tracker) == 2


async def test_track_template(hass: HomeAssistant) -> None:
    """Test tracking template."""
    specific_runs = []
    wildcard_runs = []
    wildercard_runs = []

    template_condition = Template("{{states.switch.test.state == 'on'}}", hass)
    template_condition_var = Template(
        "{{states.switch.test.state == 'on' and test == 5}}", hass
    )

    hass.states.async_set("switch.test", "off")

    def specific_run_callback(entity_id, old_state, new_state):
        specific_runs.append(1)

    async_track_template(hass, template_condition, specific_run_callback)

    @ha.callback
    def wildcard_run_callback(entity_id, old_state, new_state):
        wildcard_runs.append((old_state, new_state))

    async_track_template(hass, template_condition, wildcard_run_callback)

    async def wildercard_run_callback(entity_id, old_state, new_state):
        wildercard_runs.append((old_state, new_state))

    async_track_template(
        hass, template_condition_var, wildercard_run_callback, {"test": 5}
    )

    hass.states.async_set("switch.test", "on")
    await hass.async_block_till_done()

    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    hass.states.async_set("switch.test", "on")
    await hass.async_block_till_done()

    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    hass.states.async_set("switch.test", "on")
    await hass.async_block_till_done()

    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 2
    assert len(wildercard_runs) == 2

    template_iterate = Template("{{ (states.switch | length) > 0 }}", hass)
    iterate_calls = []

    @ha.callback
    def iterate_callback(entity_id, old_state, new_state):
        iterate_calls.append((entity_id, old_state, new_state))

    async_track_template(hass, template_iterate, iterate_callback)
    await hass.async_block_till_done()

    hass.states.async_set("switch.new", "on")
    await hass.async_block_till_done()

    assert len(iterate_calls) == 1
    assert iterate_calls[0][0] == "switch.new"
    assert iterate_calls[0][1] is None
    assert iterate_calls[0][2].state == "on"


async def test_track_template_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test tracking template with error."""
    template_error = Template("{{ (states.switch | lunch) > 0 }}", hass)
    error_calls = []

    @ha.callback
    def error_callback(entity_id, old_state, new_state):
        error_calls.append((entity_id, old_state, new_state))

    async_track_template(hass, template_error, error_callback)
    await hass.async_block_till_done()

    hass.states.async_set("switch.new", "on")
    await hass.async_block_till_done()

    assert not error_calls
    assert "lunch" in caplog.text
    assert "TemplateAssertionError" in caplog.text

    caplog.clear()

    with patch.object(Template, "async_render") as render:
        render.return_value = "ok"

        hass.states.async_set("switch.not_exist", "off")
        await hass.async_block_till_done()

    assert "no filter named 'lunch'" not in caplog.text
    assert "TemplateAssertionError" not in caplog.text


async def test_track_template_error_can_recover(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test tracking template with error."""
    hass.states.async_set("switch.data_system", "cow", {"opmode": 0})
    template_error = Template(
        "{{ states.sensor.data_system.attributes['opmode'] == '0' }}", hass
    )
    error_calls = []

    @ha.callback
    def error_callback(entity_id, old_state, new_state):
        error_calls.append((entity_id, old_state, new_state))

    async_track_template(hass, template_error, error_callback)
    await hass.async_block_till_done()
    assert not error_calls

    hass.states.async_remove("switch.data_system")

    assert "UndefinedError" in caplog.text

    hass.states.async_set("switch.data_system", "cow", {"opmode": 0})

    caplog.clear()

    assert "UndefinedError" not in caplog.text


async def test_track_template_time_change(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test tracking template with time change."""
    template_error = Template("{{ utcnow().minute % 2 == 0 }}", hass)
    calls = []

    @ha.callback
    def error_callback(entity_id, old_state, new_state):
        calls.append((entity_id, old_state, new_state))

    start_time = dt_util.utcnow() + timedelta(hours=24)
    time_that_will_not_match_right_away = start_time.replace(minute=1, second=0)
    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        unsub = async_track_template(hass, template_error, error_callback)
        await hass.async_block_till_done()
        assert not calls

    first_time = start_time.replace(minute=2, second=0)
    with patch("homeassistant.util.dt.utcnow", return_value=first_time):
        async_fire_time_changed(hass, first_time)
        await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0] == (None, None, None)

    unsub()


async def test_track_template_result(hass: HomeAssistant) -> None:
    """Test tracking template."""
    specific_runs = []
    wildcard_runs = []
    wildercard_runs = []

    template_condition = Template("{{states.sensor.test.state}}", hass)
    template_condition_var = Template(
        "{{(states.sensor.test.state|int) + test }}", hass
    )

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        track_result = updates.pop()
        specific_runs.append(int(track_result.result))

    async_track_template_result(
        hass, [TrackTemplate(template_condition, None)], specific_run_callback
    )

    @ha.callback
    def wildcard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        track_result = updates.pop()
        wildcard_runs.append(
            (int(track_result.last_result or 0), int(track_result.result))
        )

    async_track_template_result(
        hass, [TrackTemplate(template_condition, None)], wildcard_run_callback
    )

    async def wildercard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        track_result = updates.pop()
        wildercard_runs.append(
            (int(track_result.last_result or 0), int(track_result.result))
        )

    async_track_template_result(
        hass,
        [TrackTemplate(template_condition_var, {"test": 5})],
        wildercard_run_callback,
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test", 5)
    await hass.async_block_till_done()

    assert specific_runs == [5]
    assert wildcard_runs == [(0, 5)]
    assert wildercard_runs == [(0, 10)]

    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert specific_runs == [5, 30]
    assert wildcard_runs == [(0, 5), (5, 30)]
    assert wildercard_runs == [(0, 10), (10, 35)]

    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 2
    assert len(wildercard_runs) == 2

    hass.states.async_set("sensor.test", 5)
    await hass.async_block_till_done()

    assert len(specific_runs) == 3
    assert len(wildcard_runs) == 3
    assert len(wildercard_runs) == 3

    hass.states.async_set("sensor.test", 5)
    await hass.async_block_till_done()

    assert len(specific_runs) == 3
    assert len(wildcard_runs) == 3
    assert len(wildercard_runs) == 3

    hass.states.async_set("sensor.test", 20)
    await hass.async_block_till_done()

    assert len(specific_runs) == 4
    assert len(wildcard_runs) == 4
    assert len(wildercard_runs) == 4


async def test_track_template_result_none(hass: HomeAssistant) -> None:
    """Test tracking template."""
    specific_runs = []
    wildcard_runs = []
    wildercard_runs = []

    template_condition = Template("{{state_attr('sensor.test', 'battery')}}", hass)
    template_condition_var = Template(
        "{{(state_attr('sensor.test', 'battery')|int(default=0)) + test }}", hass
    )

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        track_result = updates.pop()
        result = int(track_result.result) if track_result.result is not None else None
        specific_runs.append(result)

    async_track_template_result(
        hass, [TrackTemplate(template_condition, None)], specific_run_callback
    )

    @ha.callback
    def wildcard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        track_result = updates.pop()
        last_result = (
            int(track_result.last_result)
            if track_result.last_result is not None
            else None
        )
        result = int(track_result.result) if track_result.result is not None else None
        wildcard_runs.append((last_result, result))

    async_track_template_result(
        hass, [TrackTemplate(template_condition, None)], wildcard_run_callback
    )

    async def wildercard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        track_result = updates.pop()
        last_result = (
            int(track_result.last_result)
            if track_result.last_result is not None
            else None
        )
        result = int(track_result.result) if track_result.result is not None else None
        wildercard_runs.append((last_result, result))

    async_track_template_result(
        hass,
        [TrackTemplate(template_condition_var, {"test": 5})],
        wildercard_run_callback,
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test", "-")
    await hass.async_block_till_done()

    assert specific_runs == [None]
    assert wildcard_runs == [(None, None)]
    assert wildercard_runs == [(None, 5)]

    hass.states.async_set("sensor.test", "-", {"battery": 5})
    await hass.async_block_till_done()

    assert specific_runs == [None, 5]
    assert wildcard_runs == [(None, None), (None, 5)]
    assert wildercard_runs == [(None, 5), (5, 10)]


async def test_track_template_result_super_template(hass: HomeAssistant) -> None:
    """Test tracking template with super template listening to same entity."""
    specific_runs = []
    specific_runs_availability = []
    wildcard_runs = []
    wildcard_runs_availability = []
    wildercard_runs = []
    wildercard_runs_availability = []

    template_availability = Template("{{ is_number(states('sensor.test')) }}", hass)
    template_condition = Template("{{states.sensor.test.state}}", hass)
    template_condition_var = Template(
        "{{(states.sensor.test.state|int) + test }}", hass
    )

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition:
                specific_runs.append(int(track_result.result))
            elif track_result.template is template_availability:
                specific_runs_availability.append(track_result.result)

    async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition, None),
        ],
        specific_run_callback,
        has_super_template=True,
    )

    @ha.callback
    def wildcard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition:
                wildcard_runs.append(
                    (int(track_result.last_result or 0), int(track_result.result))
                )
            elif track_result.template is template_availability:
                wildcard_runs_availability.append(track_result.result)

    async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition, None),
        ],
        wildcard_run_callback,
        has_super_template=True,
    )

    async def wildercard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition_var:
                wildercard_runs.append(
                    (int(track_result.last_result or 0), int(track_result.result))
                )
            elif track_result.template is template_availability:
                wildercard_runs_availability.append(track_result.result)

    async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition_var, {"test": 5}),
        ],
        wildercard_run_callback,
        has_super_template=True,
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test", "unavailable")
    await hass.async_block_till_done()

    assert specific_runs_availability == [False]
    assert wildcard_runs_availability == [False]
    assert wildercard_runs_availability == [False]
    assert specific_runs == []
    assert wildcard_runs == []
    assert wildercard_runs == []

    hass.states.async_set("sensor.test", 5)
    await hass.async_block_till_done()

    assert specific_runs_availability == [False, True]
    assert wildcard_runs_availability == [False, True]
    assert wildercard_runs_availability == [False, True]
    assert specific_runs == [5]
    assert wildcard_runs == [(0, 5)]
    assert wildercard_runs == [(0, 10)]

    hass.states.async_set("sensor.test", "unknown")
    await hass.async_block_till_done()

    assert specific_runs_availability == [False, True, False]
    assert wildcard_runs_availability == [False, True, False]
    assert wildercard_runs_availability == [False, True, False]

    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert specific_runs_availability == [False, True, False, True]
    assert wildcard_runs_availability == [False, True, False, True]
    assert wildercard_runs_availability == [False, True, False, True]

    assert specific_runs == [5, 30]
    assert wildcard_runs == [(0, 5), (5, 30)]
    assert wildercard_runs == [(0, 10), (10, 35)]

    hass.states.async_set("sensor.test", "other")
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 2
    assert len(wildercard_runs) == 2
    assert len(specific_runs_availability) == 6
    assert len(wildcard_runs_availability) == 6
    assert len(wildercard_runs_availability) == 6

    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 2
    assert len(wildercard_runs) == 2
    assert len(specific_runs_availability) == 6
    assert len(wildcard_runs_availability) == 6
    assert len(wildercard_runs_availability) == 6

    hass.states.async_set("sensor.test", 31)
    await hass.async_block_till_done()

    assert len(specific_runs) == 3
    assert len(wildcard_runs) == 3
    assert len(wildercard_runs) == 3
    assert len(specific_runs_availability) == 6
    assert len(wildcard_runs_availability) == 6
    assert len(wildercard_runs_availability) == 6


async def test_track_template_result_super_template_initially_false(
    hass: HomeAssistant,
) -> None:
    """Test tracking template with super template listening to same entity."""
    specific_runs = []
    specific_runs_availability = []
    wildcard_runs = []
    wildcard_runs_availability = []
    wildercard_runs = []
    wildercard_runs_availability = []

    template_availability = Template("{{ is_number(states('sensor.test')) }}", hass)
    template_condition = Template("{{states.sensor.test.state}}", hass)
    template_condition_var = Template(
        "{{(states.sensor.test.state|int) + test }}", hass
    )

    # Make the super template initially false
    hass.states.async_set("sensor.test", "unavailable")
    await hass.async_block_till_done()

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition:
                specific_runs.append(int(track_result.result))
            elif track_result.template is template_availability:
                specific_runs_availability.append(track_result.result)

    async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition, None),
        ],
        specific_run_callback,
        has_super_template=True,
    )

    @ha.callback
    def wildcard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition:
                wildcard_runs.append(
                    (int(track_result.last_result or 0), int(track_result.result))
                )
            elif track_result.template is template_availability:
                wildcard_runs_availability.append(track_result.result)

    async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition, None),
        ],
        wildcard_run_callback,
        has_super_template=True,
    )

    async def wildercard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition_var:
                wildercard_runs.append(
                    (int(track_result.last_result or 0), int(track_result.result))
                )
            elif track_result.template is template_availability:
                wildercard_runs_availability.append(track_result.result)

    async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition_var, {"test": 5}),
        ],
        wildercard_run_callback,
        has_super_template=True,
    )
    await hass.async_block_till_done()

    assert specific_runs_availability == []
    assert wildcard_runs_availability == []
    assert wildercard_runs_availability == []
    assert specific_runs == []
    assert wildcard_runs == []
    assert wildercard_runs == []

    hass.states.async_set("sensor.test", 5)
    await hass.async_block_till_done()

    assert specific_runs_availability == [True]
    assert wildcard_runs_availability == [True]
    assert wildercard_runs_availability == [True]
    assert specific_runs == [5]
    assert wildcard_runs == [(0, 5)]
    assert wildercard_runs == [(0, 10)]

    hass.states.async_set("sensor.test", "unknown")
    await hass.async_block_till_done()

    assert specific_runs_availability == [True, False]
    assert wildcard_runs_availability == [True, False]
    assert wildercard_runs_availability == [True, False]

    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert specific_runs_availability == [True, False, True]
    assert wildcard_runs_availability == [True, False, True]
    assert wildercard_runs_availability == [True, False, True]

    assert specific_runs == [5, 30]
    assert wildcard_runs == [(0, 5), (5, 30)]
    assert wildercard_runs == [(0, 10), (10, 35)]

    hass.states.async_set("sensor.test", "other")
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 2
    assert len(wildercard_runs) == 2
    assert len(specific_runs_availability) == 5
    assert len(wildcard_runs_availability) == 5
    assert len(wildercard_runs_availability) == 5

    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 2
    assert len(wildercard_runs) == 2
    assert len(specific_runs_availability) == 5
    assert len(wildcard_runs_availability) == 5
    assert len(wildercard_runs_availability) == 5

    hass.states.async_set("sensor.test", 31)
    await hass.async_block_till_done()

    assert len(specific_runs) == 3
    assert len(wildcard_runs) == 3
    assert len(wildercard_runs) == 3
    assert len(specific_runs_availability) == 5
    assert len(wildcard_runs_availability) == 5
    assert len(wildercard_runs_availability) == 5


@pytest.mark.parametrize(
    "availability_template",
    [
        "{{ states('sensor.test2') != 'unavailable' }}",
        "{% if states('sensor.test2') != 'unavailable' -%} true {%- else -%} false {%- endif %}",
        "{% if states('sensor.test2') != 'unavailable' -%} 1 {%- else -%} 0 {%- endif %}",
        "{% if states('sensor.test2') != 'unavailable' -%} yes {%- else -%} no {%- endif %}",
        "{% if states('sensor.test2') != 'unavailable' -%} on {%- else -%} off {%- endif %}",
        "{% if states('sensor.test2') != 'unavailable' -%} enable {%- else -%} disable {%- endif %}",
        # This will throw when sensor.test2 is not "unavailable"
        "{% if states('sensor.test2') != 'unavailable' -%} {{'a' + 5}} {%- else -%} false {%- endif %}",
    ],
)
async def test_track_template_result_super_template_2(
    hass: HomeAssistant, availability_template: str
) -> None:
    """Test tracking template with super template listening to different entities."""
    specific_runs = []
    specific_runs_availability = []
    wildcard_runs = []
    wildcard_runs_availability = []
    wildercard_runs = []
    wildercard_runs_availability = []

    template_availability = Template(availability_template)
    template_condition = Template("{{states.sensor.test.state}}", hass)
    template_condition_var = Template(
        "{{(states.sensor.test.state|int) + test }}", hass
    )

    def _super_template_as_boolean(result):
        if isinstance(result, TemplateError):
            return True

        return result_as_boolean(result)

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition:
                specific_runs.append(int(track_result.result))
            elif track_result.template is template_availability:
                specific_runs_availability.append(
                    _super_template_as_boolean(track_result.result)
                )

    info = async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition, None),
        ],
        specific_run_callback,
        has_super_template=True,
    )

    @ha.callback
    def wildcard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition:
                wildcard_runs.append(
                    (int(track_result.last_result or 0), int(track_result.result))
                )
            elif track_result.template is template_availability:
                wildcard_runs_availability.append(
                    _super_template_as_boolean(track_result.result)
                )

    info2 = async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition, None),
        ],
        wildcard_run_callback,
        has_super_template=True,
    )

    async def wildercard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition_var:
                wildercard_runs.append(
                    (int(track_result.last_result or 0), int(track_result.result))
                )
            elif track_result.template is template_availability:
                wildercard_runs_availability.append(
                    _super_template_as_boolean(track_result.result)
                )

    info3 = async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition_var, {"test": 5}),
        ],
        wildercard_run_callback,
        has_super_template=True,
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test2", "unavailable")
    await hass.async_block_till_done()

    assert specific_runs_availability == [False]
    assert wildcard_runs_availability == [False]
    assert wildercard_runs_availability == [False]
    assert specific_runs == []
    assert wildcard_runs == []
    assert wildercard_runs == []

    hass.states.async_set("sensor.test", 5)
    hass.states.async_set("sensor.test2", "available")
    await hass.async_block_till_done()

    assert specific_runs_availability == [False, True]
    assert wildcard_runs_availability == [False, True]
    assert wildercard_runs_availability == [False, True]
    assert specific_runs == [5]
    assert wildcard_runs == [(0, 5)]
    assert wildercard_runs == [(0, 10)]

    hass.states.async_set("sensor.test2", "unknown")
    await hass.async_block_till_done()

    assert specific_runs_availability == [False, True]
    assert wildcard_runs_availability == [False, True]
    assert wildercard_runs_availability == [False, True]

    hass.states.async_set("sensor.test2", "available")
    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert specific_runs_availability == [False, True]
    assert wildcard_runs_availability == [False, True]
    assert wildercard_runs_availability == [False, True]
    assert specific_runs == [5, 30]
    assert wildcard_runs == [(0, 5), (5, 30)]
    assert wildercard_runs == [(0, 10), (10, 35)]

    info.async_remove()
    info2.async_remove()
    info3.async_remove()


@pytest.mark.parametrize(
    "availability_template",
    [
        "{{ states('sensor.test2') != 'unavailable' }}",
        "{% if states('sensor.test2') != 'unavailable' -%} true {%- else -%} false {%- endif %}",
        "{% if states('sensor.test2') != 'unavailable' -%} 1 {%- else -%} 0 {%- endif %}",
        "{% if states('sensor.test2') != 'unavailable' -%} yes {%- else -%} no {%- endif %}",
        "{% if states('sensor.test2') != 'unavailable' -%} on {%- else -%} off {%- endif %}",
        "{% if states('sensor.test2') != 'unavailable' -%} enable {%- else -%} disable {%- endif %}",
        # This will throw when sensor.test2 is not "unavailable"
        "{% if states('sensor.test2') != 'unavailable' -%} {{'a' + 5}} {%- else -%} false {%- endif %}",
    ],
)
async def test_track_template_result_super_template_2_initially_false(
    hass: HomeAssistant, availability_template: str
) -> None:
    """Test tracking template with super template listening to different entities."""
    specific_runs = []
    specific_runs_availability = []
    wildcard_runs = []
    wildcard_runs_availability = []
    wildercard_runs = []
    wildercard_runs_availability = []

    template_availability = Template(availability_template)
    template_condition = Template("{{states.sensor.test.state}}", hass)
    template_condition_var = Template(
        "{{(states.sensor.test.state|int) + test }}", hass
    )

    hass.states.async_set("sensor.test2", "unavailable")
    await hass.async_block_till_done()

    def _super_template_as_boolean(result):
        if isinstance(result, TemplateError):
            return True

        return result_as_boolean(result)

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition:
                specific_runs.append(int(track_result.result))
            elif track_result.template is template_availability:
                specific_runs_availability.append(
                    _super_template_as_boolean(track_result.result)
                )

    info = async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition, None),
        ],
        specific_run_callback,
        has_super_template=True,
    )

    @ha.callback
    def wildcard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition:
                wildcard_runs.append(
                    (int(track_result.last_result or 0), int(track_result.result))
                )
            elif track_result.template is template_availability:
                wildcard_runs_availability.append(
                    _super_template_as_boolean(track_result.result)
                )

    info2 = async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition, None),
        ],
        wildcard_run_callback,
        has_super_template=True,
    )

    async def wildercard_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_condition_var:
                wildercard_runs.append(
                    (int(track_result.last_result or 0), int(track_result.result))
                )
            elif track_result.template is template_availability:
                wildercard_runs_availability.append(
                    _super_template_as_boolean(track_result.result)
                )

    info3 = async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_condition_var, {"test": 5}),
        ],
        wildercard_run_callback,
        has_super_template=True,
    )
    await hass.async_block_till_done()

    assert specific_runs_availability == []
    assert wildcard_runs_availability == []
    assert wildercard_runs_availability == []
    assert specific_runs == []
    assert wildcard_runs == []
    assert wildercard_runs == []

    hass.states.async_set("sensor.test", 5)
    hass.states.async_set("sensor.test2", "available")
    await hass.async_block_till_done()

    assert specific_runs_availability == [True]
    assert wildcard_runs_availability == [True]
    assert wildercard_runs_availability == [True]
    assert specific_runs == [5]
    assert wildcard_runs == [(0, 5)]
    assert wildercard_runs == [(0, 10)]

    hass.states.async_set("sensor.test2", "unknown")
    await hass.async_block_till_done()

    assert specific_runs_availability == [True]
    assert wildcard_runs_availability == [True]
    assert wildercard_runs_availability == [True]

    hass.states.async_set("sensor.test2", "available")
    hass.states.async_set("sensor.test", 30)
    await hass.async_block_till_done()

    assert specific_runs_availability == [True]
    assert wildcard_runs_availability == [True]
    assert wildercard_runs_availability == [True]
    assert specific_runs == [5, 30]
    assert wildcard_runs == [(0, 5), (5, 30)]
    assert wildercard_runs == [(0, 10), (10, 35)]

    info.async_remove()
    info2.async_remove()
    info3.async_remove()


async def test_track_template_result_complex(hass: HomeAssistant) -> None:
    """Test tracking template."""
    specific_runs = []
    template_complex_str = """
{% if states("sensor.domain") == "light" %}
  {{ states.light | map(attribute='entity_id') | list }}
{% elif states("sensor.domain") == "lock" %}
  {{ states.lock | map(attribute='entity_id') | list }}
{% elif states("sensor.domain") == "single_binary_sensor" %}
  {{ states("binary_sensor.single") }}
{% else %}
  {{ states | map(attribute='entity_id') | list }}
{% endif %}

"""
    template_complex = Template(template_complex_str, hass)

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        specific_runs.append(updates.pop().result)

    hass.states.async_set("light.one", "on")
    hass.states.async_set("lock.one", "locked")

    info = async_track_template_result(
        hass,
        [TrackTemplate(template_complex, None, timedelta(seconds=0))],
        specific_run_callback,
    )
    await hass.async_block_till_done()

    assert info.listeners == {
        "all": True,
        "domains": set(),
        "entities": set(),
        "time": False,
    }

    hass.states.async_set("sensor.domain", "light")
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert specific_runs[0] == ["light.one"]

    assert info.listeners == {
        "all": False,
        "domains": {"light"},
        "entities": {"sensor.domain"},
        "time": False,
    }

    hass.states.async_set("sensor.domain", "lock")
    await hass.async_block_till_done()
    assert len(specific_runs) == 2
    assert specific_runs[1] == ["lock.one"]
    assert info.listeners == {
        "all": False,
        "domains": {"lock"},
        "entities": {"sensor.domain"},
        "time": False,
    }

    hass.states.async_set("sensor.domain", "all")
    await hass.async_block_till_done()
    assert len(specific_runs) == 3
    assert "light.one" in specific_runs[2]
    assert "lock.one" in specific_runs[2]
    assert "sensor.domain" in specific_runs[2]
    assert info.listeners == {
        "all": True,
        "domains": set(),
        "entities": set(),
        "time": False,
    }

    hass.states.async_set("sensor.domain", "light")
    await hass.async_block_till_done()
    assert len(specific_runs) == 4
    assert specific_runs[3] == ["light.one"]
    assert info.listeners == {
        "all": False,
        "domains": {"light"},
        "entities": {"sensor.domain"},
        "time": False,
    }

    hass.states.async_set("light.two", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 5
    assert "light.one" in specific_runs[4]
    assert "light.two" in specific_runs[4]
    assert "sensor.domain" not in specific_runs[4]
    assert info.listeners == {
        "all": False,
        "domains": {"light"},
        "entities": {"sensor.domain"},
        "time": False,
    }

    hass.states.async_set("light.three", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 6
    assert "light.one" in specific_runs[5]
    assert "light.two" in specific_runs[5]
    assert "light.three" in specific_runs[5]
    assert "sensor.domain" not in specific_runs[5]
    assert info.listeners == {
        "all": False,
        "domains": {"light"},
        "entities": {"sensor.domain"},
        "time": False,
    }

    hass.states.async_set("sensor.domain", "lock")
    await hass.async_block_till_done()
    assert len(specific_runs) == 7
    assert specific_runs[6] == ["lock.one"]
    assert info.listeners == {
        "all": False,
        "domains": {"lock"},
        "entities": {"sensor.domain"},
        "time": False,
    }

    hass.states.async_set("sensor.domain", "single_binary_sensor")
    await hass.async_block_till_done()
    assert len(specific_runs) == 8
    assert specific_runs[7] == "unknown"
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"binary_sensor.single", "sensor.domain"},
        "time": False,
    }

    hass.states.async_set("binary_sensor.single", "binary_sensor_on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 9
    assert specific_runs[8] == "binary_sensor_on"
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"binary_sensor.single", "sensor.domain"},
        "time": False,
    }

    hass.states.async_set("sensor.domain", "lock")
    await hass.async_block_till_done()
    assert len(specific_runs) == 10
    assert specific_runs[9] == ["lock.one"]
    assert info.listeners == {
        "all": False,
        "domains": {"lock"},
        "entities": {"sensor.domain"},
        "time": False,
    }


async def test_track_template_result_with_wildcard(hass: HomeAssistant) -> None:
    """Test tracking template with a wildcard."""
    specific_runs = []
    template_complex_str = r"""

{% for state in states %}
  {% if state.entity_id | regex_match('.*\\.office_') %}
    {{ state.entity_id }}={{ state.state }}
  {% endif %}
{% endfor %}

"""
    template_complex = Template(template_complex_str, hass)

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        specific_runs.append(updates.pop().result)

    hass.states.async_set("cover.office_drapes", "closed")
    hass.states.async_set("cover.office_window", "closed")
    hass.states.async_set("cover.office_skylight", "open")

    info = async_track_template_result(
        hass, [TrackTemplate(template_complex, None)], specific_run_callback
    )
    await hass.async_block_till_done()

    hass.states.async_set("cover.office_window", "open")
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert info.listeners == {
        "all": True,
        "domains": set(),
        "entities": set(),
        "time": False,
    }

    assert "cover.office_drapes=closed" in specific_runs[0]
    assert "cover.office_window=open" in specific_runs[0]
    assert "cover.office_skylight=open" in specific_runs[0]


async def test_track_template_result_with_group(hass: HomeAssistant) -> None:
    """Test tracking template with a group."""
    hass.states.async_set("sensor.power_1", 0)
    hass.states.async_set("sensor.power_2", 200.2)
    hass.states.async_set("sensor.power_3", 400.4)
    hass.states.async_set("sensor.power_4", 800.8)

    assert await async_setup_component(
        hass,
        "group",
        {"group": {"power_sensors": "sensor.power_1,sensor.power_2,sensor.power_3"}},
    )
    await hass.async_block_till_done()

    assert hass.states.get("group.power_sensors")
    assert hass.states.get("group.power_sensors").state

    specific_runs = []
    template_complex_str = r"""

{{ states.group.power_sensors.attributes.entity_id | expand | map(attribute='state')|map('float')|sum  }}

"""
    template_complex = Template(template_complex_str, hass)

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        specific_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass, [TrackTemplate(template_complex, None)], specific_run_callback
    )
    await hass.async_block_till_done()

    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {
            "group.power_sensors",
            "sensor.power_1",
            "sensor.power_2",
            "sensor.power_3",
        },
        "time": False,
    }

    hass.states.async_set("sensor.power_1", 100.1)
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    assert specific_runs[0] == 100.1 + 200.2 + 400.4

    hass.states.async_set("sensor.power_3", 0)
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    assert specific_runs[1] == 100.1 + 200.2 + 0

    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={
            "group": {
                "power_sensors": "sensor.power_1,sensor.power_2,sensor.power_3,sensor.power_4",
            }
        },
    ):
        await hass.services.async_call("group", "reload")
        await hass.async_block_till_done()

    info.async_refresh()
    await hass.async_block_till_done()
    assert specific_runs[-1] == 100.1 + 200.2 + 0 + 800.8


async def test_track_template_result_and_conditional(hass: HomeAssistant) -> None:
    """Test tracking template with an and conditional."""
    specific_runs = []
    hass.states.async_set("light.a", "off")
    hass.states.async_set("light.b", "off")
    template_str = '{% if states.light.a.state == "on" and states.light.b.state == "on" %}on{% else %}off{% endif %}'

    template = Template(template_str, hass)

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        specific_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass, [TrackTemplate(template, None)], specific_run_callback
    )
    await hass.async_block_till_done()
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"light.a"},
        "time": False,
    }

    hass.states.async_set("light.b", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    hass.states.async_set("light.a", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert specific_runs[0] == "on"
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"light.a", "light.b"},
        "time": False,
    }

    hass.states.async_set("light.b", "off")
    await hass.async_block_till_done()
    assert len(specific_runs) == 2
    assert specific_runs[1] == "off"
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"light.a", "light.b"},
        "time": False,
    }

    hass.states.async_set("light.a", "off")
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    hass.states.async_set("light.b", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    hass.states.async_set("light.a", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 3
    assert specific_runs[2] == "on"


async def test_track_template_result_and_conditional_upper_case(
    hass: HomeAssistant,
) -> None:
    """Test tracking template with an and conditional with an upper case template."""
    specific_runs = []
    hass.states.async_set("light.a", "off")
    hass.states.async_set("light.b", "off")
    template_str = '{% if states.light.A.state == "on" and states.light.B.state == "on" %}on{% else %}off{% endif %}'

    template = Template(template_str, hass)

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        specific_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass, [TrackTemplate(template, None)], specific_run_callback
    )
    await hass.async_block_till_done()
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"light.a"},
        "time": False,
    }

    hass.states.async_set("light.b", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    hass.states.async_set("light.a", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert specific_runs[0] == "on"
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"light.a", "light.b"},
        "time": False,
    }

    hass.states.async_set("light.b", "off")
    await hass.async_block_till_done()
    assert len(specific_runs) == 2
    assert specific_runs[1] == "off"
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"light.a", "light.b"},
        "time": False,
    }

    hass.states.async_set("light.a", "off")
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    hass.states.async_set("light.b", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    hass.states.async_set("light.a", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 3
    assert specific_runs[2] == "on"


async def test_track_template_result_iterator(hass: HomeAssistant) -> None:
    """Test tracking template."""
    iterator_runs = []

    @ha.callback
    def iterator_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        iterator_runs.append(updates.pop().result)

    async_track_template_result(
        hass,
        [
            TrackTemplate(
                Template(
                    """
            {% for state in states.sensor %}
                {% if state.state == 'on' %}
                    {{ state.entity_id }},
                {% endif %}
            {% endfor %}
            """,
                    hass,
                ),
                None,
                timedelta(seconds=0),
            )
        ],
        iterator_callback,
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test", 5)
    await hass.async_block_till_done()

    assert iterator_runs == [""]

    filter_runs = []

    @ha.callback
    def filter_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        filter_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass,
        [
            TrackTemplate(
                Template(
                    """{{ states.sensor|selectattr("state","equalto","on")
                |join(",", attribute="entity_id") }}""",
                    hass,
                ),
                None,
                timedelta(seconds=0),
            )
        ],
        filter_callback,
    )
    await hass.async_block_till_done()
    assert info.listeners == {
        "all": False,
        "domains": {"sensor"},
        "entities": set(),
        "time": False,
    }

    hass.states.async_set("sensor.test", 6)
    await hass.async_block_till_done()

    assert filter_runs == [""]
    assert iterator_runs == [""]

    hass.states.async_set("sensor.new", "on")
    await hass.async_block_till_done()
    assert iterator_runs == ["", "sensor.new,"]
    assert filter_runs == ["", "sensor.new"]


async def test_track_template_result_errors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test tracking template with errors in the template."""
    template_syntax_error = Template("{{states.switch", hass)

    template_not_exist = Template("{{states.switch.not_exist.state }}", hass)

    syntax_error_runs = []
    not_exist_runs = []

    @ha.callback
    def syntax_error_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        track_result = updates.pop()
        syntax_error_runs.append(
            (
                event,
                track_result.template,
                track_result.last_result,
                track_result.result,
            )
        )

    async_track_template_result(
        hass, [TrackTemplate(template_syntax_error, None)], syntax_error_listener
    )
    await hass.async_block_till_done()

    assert len(syntax_error_runs) == 0
    assert "TemplateSyntaxError" in caplog.text

    @ha.callback
    def not_exist_runs_error_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        template_track = updates.pop()
        not_exist_runs.append(
            (
                event,
                template_track.template,
                template_track.last_result,
                template_track.result,
            )
        )

    async_track_template_result(
        hass,
        [TrackTemplate(template_not_exist, None)],
        not_exist_runs_error_listener,
    )
    await hass.async_block_till_done()

    assert len(syntax_error_runs) == 0
    assert len(not_exist_runs) == 0

    hass.states.async_set("switch.not_exist", "off")
    await hass.async_block_till_done()

    assert len(not_exist_runs) == 1
    assert not_exist_runs[0][0].data.get("entity_id") == "switch.not_exist"
    assert not_exist_runs[0][1] == template_not_exist
    assert not_exist_runs[0][2] is None
    assert not_exist_runs[0][3] == "off"

    hass.states.async_set("switch.not_exist", "on")
    await hass.async_block_till_done()

    assert len(syntax_error_runs) == 0
    assert len(not_exist_runs) == 2
    assert not_exist_runs[1][0].data.get("entity_id") == "switch.not_exist"
    assert not_exist_runs[1][1] == template_not_exist
    assert not_exist_runs[1][2] == "off"
    assert not_exist_runs[1][3] == "on"

    with patch.object(Template, "async_render") as render:
        render.side_effect = TemplateError(jinja2.TemplateError())

        hass.states.async_set("switch.not_exist", "off")
        await hass.async_block_till_done()

        assert len(not_exist_runs) == 3
        assert not_exist_runs[2][0].data.get("entity_id") == "switch.not_exist"
        assert not_exist_runs[2][1] == template_not_exist
        assert not_exist_runs[2][2] == "on"
        assert isinstance(not_exist_runs[2][3], TemplateError)


async def test_track_template_result_transient_errors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test tracking template with transient errors in the template."""
    hass.states.async_set("sensor.error", "unknown")
    template_that_raises_sometimes = Template(
        "{{ states('sensor.error') | float }}", hass
    )

    sometimes_error_runs = []

    @ha.callback
    def sometimes_error_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        track_result = updates.pop()
        sometimes_error_runs.append(
            (
                event,
                track_result.template,
                track_result.last_result,
                track_result.result,
            )
        )

    info = async_track_template_result(
        hass,
        [TrackTemplate(template_that_raises_sometimes, None)],
        sometimes_error_listener,
    )
    await hass.async_block_till_done()

    assert sometimes_error_runs == []
    assert "ValueError" in caplog.text
    assert "ValueError" in repr(info)
    caplog.clear()

    hass.states.async_set("sensor.error", "unavailable")
    await hass.async_block_till_done()
    assert len(sometimes_error_runs) == 1
    assert isinstance(sometimes_error_runs[0][3], TemplateError)
    sometimes_error_runs.clear()
    assert "ValueError" in repr(info)

    hass.states.async_set("sensor.error", "4")
    await hass.async_block_till_done()
    assert len(sometimes_error_runs) == 1
    assert sometimes_error_runs[0][3] == 4.0
    sometimes_error_runs.clear()
    assert "ValueError" not in repr(info)


async def test_static_string(hass: HomeAssistant) -> None:
    """Test a static string."""
    template_refresh = Template("{{ 'static' }}", hass)

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass, [TrackTemplate(template_refresh, None)], refresh_listener
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == ["static"]


async def test_track_template_rate_limit(hass: HomeAssistant) -> None:
    """Test template rate limit."""
    template_refresh = Template("{{ states | count }}", hass)

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass,
        [TrackTemplate(template_refresh, None, timedelta(seconds=0.1))],
        refresh_listener,
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == [0]
    hass.states.async_set("sensor.one", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0]
    info.async_refresh()
    assert refresh_runs == [0, 1]
    hass.states.async_set("sensor.TWO", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 2]
    hass.states.async_set("sensor.three", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 2]
    hass.states.async_set("sensor.fOuR", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 2]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125 * 2)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 2, 4]
    hass.states.async_set("sensor.five", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 2, 4]

    info.async_remove()


async def test_track_template_rate_limit_super(hass: HomeAssistant) -> None:
    """Test template rate limit with super template."""
    template_availability = Template(
        "{{ states('sensor.one') != 'unavailable' }}", hass
    )
    template_refresh = Template("{{ states | count }}", hass)

    availability_runs = []
    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_refresh:
                refresh_runs.append(track_result.result)
            elif track_result.template is template_availability:
                availability_runs.append(track_result.result)

    info = async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None),
            TrackTemplate(template_refresh, None, timedelta(seconds=0.1)),
        ],
        refresh_listener,
        has_super_template=True,
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == [0]
    hass.states.async_set("sensor.one", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0]
    info.async_refresh()
    assert refresh_runs == [0, 1]
    hass.states.async_set("sensor.two", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1]
    hass.states.async_set("sensor.one", "unavailable")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    assert refresh_runs == [0, 1]
    hass.states.async_set("sensor.three", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1]
    hass.states.async_set("sensor.four", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1]
    # The super template renders as true -> trigger rerendering of all templates
    hass.states.async_set("sensor.one", "available")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 4]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125 * 2)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 4]
    hass.states.async_set("sensor.five", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 4]

    info.async_remove()


async def test_track_template_rate_limit_super_2(hass: HomeAssistant) -> None:
    """Test template rate limit with rate limited super template."""
    # Somewhat forced example of a rate limited template
    template_availability = Template("{{ states | count % 2 == 1 }}", hass)
    template_refresh = Template("{{ states | count }}", hass)

    availability_runs = []
    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_refresh:
                refresh_runs.append(track_result.result)
            elif track_result.template is template_availability:
                availability_runs.append(track_result.result)

    info = async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None, timedelta(seconds=0.1)),
            TrackTemplate(template_refresh, None, timedelta(seconds=0.1)),
        ],
        refresh_listener,
        has_super_template=True,
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == []
    hass.states.async_set("sensor.one", "any")
    await hass.async_block_till_done()
    assert refresh_runs == []
    info.async_refresh()
    assert refresh_runs == [1]
    hass.states.async_set("sensor.two", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    assert refresh_runs == [1]
    hass.states.async_set("sensor.three", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1]
    hass.states.async_set("sensor.four", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1]
    hass.states.async_set("sensor.five", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125 * 2)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    assert refresh_runs == [1, 5]
    hass.states.async_set("sensor.six", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1, 5]

    info.async_remove()


async def test_track_template_rate_limit_super_3(hass: HomeAssistant) -> None:
    """Test template with rate limited super template."""
    # Somewhat forced example of a rate limited template
    template_availability = Template("{{ states | count % 2 == 1 }}", hass)
    template_refresh = Template("{{ states | count }}", hass)

    availability_runs = []
    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for track_result in updates:
            if track_result.template is template_refresh:
                refresh_runs.append(track_result.result)
            elif track_result.template is template_availability:
                availability_runs.append(track_result.result)

    info = async_track_template_result(
        hass,
        [
            TrackTemplate(template_availability, None, timedelta(seconds=0.1)),
            TrackTemplate(template_refresh, None),
        ],
        refresh_listener,
        has_super_template=True,
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == []
    hass.states.async_set("sensor.ONE", "any")
    await hass.async_block_till_done()
    assert refresh_runs == []
    info.async_refresh()
    assert refresh_runs == [1]
    hass.states.async_set("sensor.two", "any")
    await hass.async_block_till_done()
    # The super template is rate limited so stuck at `True`
    assert refresh_runs == [1, 2]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    assert refresh_runs == [1, 2]
    hass.states.async_set("sensor.three", "any")
    await hass.async_block_till_done()
    # The super template is rate limited so stuck at `False`
    assert refresh_runs == [1, 2]
    hass.states.async_set("sensor.four", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1, 2]
    hass.states.async_set("sensor.FIVE", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1, 2]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125 * 2)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    assert refresh_runs == [1, 2, 5]
    hass.states.async_set("sensor.six", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1, 2, 5, 6]
    hass.states.async_set("sensor.seven", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1, 2, 5, 6, 7]

    info.async_remove()


async def test_track_template_rate_limit_suppress_listener(hass: HomeAssistant) -> None:
    """Test template rate limit will suppress the listener during the rate limit."""
    template_refresh = Template("{{ states | count }}", hass)

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass,
        [TrackTemplate(template_refresh, None, timedelta(seconds=0.1))],
        refresh_listener,
    )
    await hass.async_block_till_done()
    info.async_refresh()

    assert info.listeners == {
        "all": True,
        "domains": set(),
        "entities": set(),
        "time": False,
    }
    await hass.async_block_till_done()

    assert refresh_runs == [0]
    hass.states.async_set("sensor.oNe", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0]
    info.async_refresh()
    assert refresh_runs == [0, 1]
    hass.states.async_set("sensor.two", "any")
    await hass.async_block_till_done()
    # Should be suppressed during the rate limit
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": set(),
        "time": False,
    }
    assert refresh_runs == [0, 1]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    # Rate limit released and the all listener returns
    assert info.listeners == {
        "all": True,
        "domains": set(),
        "entities": set(),
        "time": False,
    }
    assert refresh_runs == [0, 1, 2]
    hass.states.async_set("sensor.Three", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 2]
    hass.states.async_set("sensor.four", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1, 2]
    # Rate limit hit and the all listener is shut off
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": set(),
        "time": False,
    }
    next_time = dt_util.utcnow() + timedelta(seconds=0.125 * 2)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    # Rate limit released and the all listener returns
    assert info.listeners == {
        "all": True,
        "domains": set(),
        "entities": set(),
        "time": False,
    }
    assert refresh_runs == [0, 1, 2, 4]
    hass.states.async_set("sensor.Five", "any")
    await hass.async_block_till_done()
    # Rate limit hit and the all listener is shut off
    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": set(),
        "time": False,
    }
    assert refresh_runs == [0, 1, 2, 4]

    info.async_remove()


async def test_track_template_rate_limit_five(hass: HomeAssistant) -> None:
    """Test template rate limit of 5 seconds."""
    template_refresh = Template("{{ states | count }}", hass)

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass,
        [TrackTemplate(template_refresh, None, timedelta(seconds=5))],
        refresh_listener,
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == [0]
    hass.states.async_set("sensor.one", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0]
    info.async_refresh()
    assert refresh_runs == [0, 1]
    hass.states.async_set("sensor.two", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1]
    hass.states.async_set("sensor.three", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [0, 1]

    info.async_remove()


async def test_track_template_has_default_rate_limit(hass: HomeAssistant) -> None:
    """Test template has a rate limit by default."""
    hass.states.async_set("sensor.zero", "any")
    template_refresh = Template("{{ states | list | count }}", hass)

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass,
        [TrackTemplate(template_refresh, None)],
        refresh_listener,
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == [1]
    hass.states.async_set("sensor.one", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1]
    info.async_refresh()
    assert refresh_runs == [1, 2]
    hass.states.async_set("sensor.two", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1, 2]
    hass.states.async_set("sensor.three", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1, 2]

    info.async_remove()


async def test_track_template_unavailable_states_has_default_rate_limit(
    hass: HomeAssistant,
) -> None:
    """Test template watching for unavailable states has a rate limit by default."""
    hass.states.async_set("sensor.zero", "unknown")
    template_refresh = Template(
        "{{ states | selectattr('state', 'in', ['unavailable', 'unknown', 'none']) | list | count }}",
        hass,
    )

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass,
        [TrackTemplate(template_refresh, None)],
        refresh_listener,
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == [1]
    hass.states.async_set("sensor.one", "unknown")
    await hass.async_block_till_done()
    assert refresh_runs == [1]
    info.async_refresh()
    assert refresh_runs == [1, 2]
    hass.states.async_set("sensor.two", "any")
    await hass.async_block_till_done()
    assert refresh_runs == [1, 2]
    hass.states.async_set("sensor.three", "unknown")
    await hass.async_block_till_done()
    assert refresh_runs == [1, 2]
    info.async_refresh()
    await hass.async_block_till_done()
    assert refresh_runs == [1, 2, 3]
    info.async_remove()


async def test_specifically_referenced_entity_is_not_rate_limited(
    hass: HomeAssistant,
) -> None:
    """Test template rate limit of 5 seconds."""
    hass.states.async_set("sensor.one", "none")

    template_refresh = Template('{{ states | count }}_{{ states("sensor.one") }}', hass)

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass,
        [TrackTemplate(template_refresh, None, timedelta(seconds=5))],
        refresh_listener,
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == ["1_none"]
    hass.states.async_set("sensor.one", "any")
    await hass.async_block_till_done()
    assert refresh_runs == ["1_none", "1_any"]
    info.async_refresh()
    assert refresh_runs == ["1_none", "1_any"]
    hass.states.async_set("sensor.two", "any")
    await hass.async_block_till_done()
    assert refresh_runs == ["1_none", "1_any"]
    hass.states.async_set("sensor.three", "any")
    await hass.async_block_till_done()
    assert refresh_runs == ["1_none", "1_any"]
    hass.states.async_set("sensor.one", "none")
    await hass.async_block_till_done()
    assert refresh_runs == ["1_none", "1_any", "3_none"]
    info.async_remove()


async def test_track_two_templates_with_different_rate_limits(
    hass: HomeAssistant,
) -> None:
    """Test two templates with different rate limits."""
    template_one = Template("{{ (states | count) + 0 }}", hass)
    template_five = Template("{{ states | count }}", hass)

    refresh_runs = {
        template_one: [],
        template_five: [],
    }

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for update in updates:
            refresh_runs[update.template].append(update.result)

    info = async_track_template_result(
        hass,
        [
            TrackTemplate(template_one, None, timedelta(seconds=0.1)),
            TrackTemplate(template_five, None, timedelta(seconds=5)),
        ],
        refresh_listener,
    )

    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs[template_one] == [0]
    assert refresh_runs[template_five] == [0]
    hass.states.async_set("sensor.one", "any")
    await hass.async_block_till_done()
    assert refresh_runs[template_one] == [0]
    assert refresh_runs[template_five] == [0]
    info.async_refresh()
    assert refresh_runs[template_one] == [0, 1]
    assert refresh_runs[template_five] == [0, 1]
    hass.states.async_set("sensor.two", "any")
    await hass.async_block_till_done()
    assert refresh_runs[template_one] == [0, 1]
    assert refresh_runs[template_five] == [0, 1]
    next_time = dt_util.utcnow() + timedelta(seconds=0.125 * 1)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert refresh_runs[template_one] == [0, 1, 2]
    assert refresh_runs[template_five] == [0, 1]
    hass.states.async_set("sensor.three", "any")
    await hass.async_block_till_done()
    assert refresh_runs[template_one] == [0, 1, 2]
    assert refresh_runs[template_five] == [0, 1]
    hass.states.async_set("sensor.four", "any")
    await hass.async_block_till_done()
    assert refresh_runs[template_one] == [0, 1, 2]
    assert refresh_runs[template_five] == [0, 1]
    hass.states.async_set("sensor.five", "any")
    await hass.async_block_till_done()
    assert refresh_runs[template_one] == [0, 1, 2]
    assert refresh_runs[template_five] == [0, 1]
    info.async_remove()


async def test_string(hass: HomeAssistant) -> None:
    """Test a string."""
    template_refresh = Template("no_template", hass)

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass, [TrackTemplate(template_refresh, None)], refresh_listener
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == ["no_template"]


async def test_track_template_result_refresh_cancel(hass: HomeAssistant) -> None:
    """Test cancelling and refreshing result."""
    template_refresh = Template("{{states.switch.test.state == 'on' and now() }}", hass)

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass, [TrackTemplate(template_refresh, None)], refresh_listener
    )
    await hass.async_block_till_done()

    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert refresh_runs == [False]

    assert len(refresh_runs) == 1

    info.async_refresh()
    hass.states.async_set("switch.test", "on")
    await hass.async_block_till_done()

    assert len(refresh_runs) == 2
    assert refresh_runs[0] != refresh_runs[1]

    info.async_remove()
    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert len(refresh_runs) == 2

    template_refresh = Template("{{ value }}", hass)
    refresh_runs = []

    info = async_track_template_result(
        hass,
        [TrackTemplate(template_refresh, {"value": "duck"})],
        refresh_listener,
    )
    await hass.async_block_till_done()
    info.async_refresh()
    await hass.async_block_till_done()

    assert refresh_runs == ["duck"]

    info.async_refresh()
    await hass.async_block_till_done()
    assert refresh_runs == ["duck"]


async def test_async_track_template_result_multiple_templates(
    hass: HomeAssistant,
) -> None:
    """Test tracking multiple templates."""

    template_1 = Template("{{ states.switch.test.state == 'on' }}")
    template_2 = Template("{{ states.switch.test.state == 'on' }}")
    template_3 = Template("{{ states.switch.test.state == 'off' }}")
    template_4 = Template(
        "{{ states.binary_sensor | map(attribute='entity_id') | list }}"
    )

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates)

    async_track_template_result(
        hass,
        [
            TrackTemplate(template_1, None),
            TrackTemplate(template_2, None),
            TrackTemplate(template_3, None),
            TrackTemplate(template_4, None),
        ],
        refresh_listener,
    )

    hass.states.async_set("switch.test", "on")
    await hass.async_block_till_done()

    assert refresh_runs == [
        [
            TrackTemplateResult(template_1, None, True),
            TrackTemplateResult(template_2, None, True),
            TrackTemplateResult(template_3, None, False),
        ]
    ]

    refresh_runs = []
    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert refresh_runs == [
        [
            TrackTemplateResult(template_1, True, False),
            TrackTemplateResult(template_2, True, False),
            TrackTemplateResult(template_3, False, True),
        ]
    ]

    refresh_runs = []
    hass.states.async_set("binary_sensor.test", "off")
    await hass.async_block_till_done()

    assert refresh_runs == [
        [TrackTemplateResult(template_4, None, ["binary_sensor.test"])]
    ]


async def test_async_track_template_result_multiple_templates_mixing_domain(
    hass: HomeAssistant,
) -> None:
    """Test tracking multiple templates when tracking entities and an entire domain."""

    template_1 = Template("{{ states.switch.test.state == 'on' }}")
    template_2 = Template("{{ states.switch.test.state == 'on' }}")
    template_3 = Template("{{ states.switch.test.state == 'off' }}")
    template_4 = Template(
        "{{ states.switch | sort(attribute='entity_id') | map(attribute='entity_id') | list }}"
    )

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates)

    async_track_template_result(
        hass,
        [
            TrackTemplate(template_1, None),
            TrackTemplate(template_2, None),
            TrackTemplate(template_3, None),
            TrackTemplate(template_4, None, timedelta(seconds=0)),
        ],
        refresh_listener,
    )

    hass.states.async_set("switch.test", "on")
    await hass.async_block_till_done()

    assert refresh_runs == [
        [
            TrackTemplateResult(template_1, None, True),
            TrackTemplateResult(template_2, None, True),
            TrackTemplateResult(template_3, None, False),
            TrackTemplateResult(template_4, None, ["switch.test"]),
        ]
    ]

    refresh_runs = []
    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert refresh_runs == [
        [
            TrackTemplateResult(template_1, True, False),
            TrackTemplateResult(template_2, True, False),
            TrackTemplateResult(template_3, False, True),
        ]
    ]

    refresh_runs = []
    hass.states.async_set("binary_sensor.test", "off")
    await hass.async_block_till_done()

    assert refresh_runs == []

    refresh_runs = []
    hass.states.async_set("switch.new", "off")
    await hass.async_block_till_done()

    assert refresh_runs == [
        [
            TrackTemplateResult(
                template_4, ["switch.test"], ["switch.new", "switch.test"]
            )
        ]
    ]


async def test_async_track_template_result_raise_on_template_error(
    hass: HomeAssistant,
) -> None:
    """Test that we raise as soon as we encounter a failed template."""

    with pytest.raises(TemplateError):
        async_track_template_result(
            hass,
            [
                TrackTemplate(
                    Template(
                        "{{ states.switch | function_that_does_not_exist | list }}"
                    ),
                    None,
                ),
            ],
            ha.callback(lambda event, updates: None),
            raise_on_template_error=True,
        )


async def test_track_template_with_time(hass: HomeAssistant) -> None:
    """Test tracking template with time."""

    hass.states.async_set("switch.test", "on")
    specific_runs = []
    template_complex = Template("{{ states.switch.test.state and now() }}", hass)

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        specific_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass, [TrackTemplate(template_complex, None)], specific_run_callback
    )
    await hass.async_block_till_done()

    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"switch.test"},
        "time": True,
    }

    await hass.async_block_till_done()
    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(seconds=61))
    async_fire_time_changed(hass, now + timedelta(seconds=61 * 2))
    await hass.async_block_till_done()
    assert specific_runs[-1] != specific_runs[0]
    info.async_remove()


async def test_track_template_with_time_default(hass: HomeAssistant) -> None:
    """Test tracking template with time."""

    specific_runs = []
    template_complex = Template("{{ now() }}", hass)

    def specific_run_callback(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        specific_runs.append(updates.pop().result)

    info = async_track_template_result(
        hass, [TrackTemplate(template_complex, None)], specific_run_callback
    )
    await hass.async_block_till_done()

    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": set(),
        "time": True,
    }

    await hass.async_block_till_done()
    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(seconds=2))
    async_fire_time_changed(hass, now + timedelta(seconds=4))
    await hass.async_block_till_done()
    assert len(specific_runs) < 2
    async_fire_time_changed(hass, now + timedelta(minutes=2))
    await hass.async_block_till_done()
    async_fire_time_changed(hass, now + timedelta(minutes=4))
    await hass.async_block_till_done()
    assert len(specific_runs) >= 2
    assert specific_runs[-1] != specific_runs[0]
    info.async_remove()


async def test_track_template_with_time_that_leaves_scope(hass: HomeAssistant) -> None:
    """Test tracking template with time."""
    now = dt_util.utcnow()
    test_time = datetime(now.year + 1, 5, 24, 11, 59, 1, 500000, tzinfo=dt_util.UTC)

    with patch("homeassistant.util.dt.utcnow", return_value=test_time):
        hass.states.async_set("binary_sensor.washing_machine", "on")
        specific_runs = []
        template_complex = Template(
            """
            {% if states.binary_sensor.washing_machine.state == "on" %}
                {{ now() }}
            {% else %}
                {{ states.binary_sensor.washing_machine.last_updated }}
            {% endif %}
        """,
            hass,
        )

        def specific_run_callback(
            event: EventType[EventStateChangedData] | None,
            updates: list[TrackTemplateResult],
        ) -> None:
            specific_runs.append(updates.pop().result)

        info = async_track_template_result(
            hass, [TrackTemplate(template_complex, None)], specific_run_callback
        )
        await hass.async_block_till_done()

        assert info.listeners == {
            "all": False,
            "domains": set(),
            "entities": {"binary_sensor.washing_machine"},
            "time": True,
        }

        hass.states.async_set("binary_sensor.washing_machine", "off")
        await hass.async_block_till_done()

        assert info.listeners == {
            "all": False,
            "domains": set(),
            "entities": {"binary_sensor.washing_machine"},
            "time": False,
        }

        hass.states.async_set("binary_sensor.washing_machine", "on")
        await hass.async_block_till_done()

        assert info.listeners == {
            "all": False,
            "domains": set(),
            "entities": {"binary_sensor.washing_machine"},
            "time": True,
        }

        # Verify we do not update before the minute rolls over
        callback_count_before_time_change = len(specific_runs)
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
        assert len(specific_runs) == callback_count_before_time_change

        async_fire_time_changed(hass, test_time + timedelta(seconds=58))
        await hass.async_block_till_done()
        assert len(specific_runs) == callback_count_before_time_change

        # Verify we do update on the next change of minute
        async_fire_time_changed(hass, test_time + timedelta(seconds=59))

        await hass.async_block_till_done()
        assert len(specific_runs) == callback_count_before_time_change + 1

    info.async_remove()


async def test_async_track_template_result_multiple_templates_mixing_listeners(
    hass: HomeAssistant,
) -> None:
    """Test tracking multiple templates with mixing listener types."""

    template_1 = Template("{{ states.switch.test.state == 'on' }}")
    template_2 = Template("{{ now() and True }}")

    refresh_runs = []

    @ha.callback
    def refresh_listener(
        event: EventType[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        refresh_runs.append(updates)

    now = dt_util.utcnow()

    time_that_will_not_match_right_away = datetime(
        now.year + 1, 5, 24, 11, 59, 55, tzinfo=dt_util.UTC
    )

    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        info = async_track_template_result(
            hass,
            [
                TrackTemplate(template_1, None),
                TrackTemplate(template_2, None),
            ],
            refresh_listener,
        )

    assert info.listeners == {
        "all": False,
        "domains": set(),
        "entities": {"switch.test"},
        "time": True,
    }
    hass.states.async_set("switch.test", "on")
    await hass.async_block_till_done()

    assert refresh_runs == [
        [
            TrackTemplateResult(template_1, None, True),
        ]
    ]

    refresh_runs = []
    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert refresh_runs == [
        [
            TrackTemplateResult(template_1, True, False),
        ]
    ]

    refresh_runs = []
    next_time = time_that_will_not_match_right_away + timedelta(hours=25)
    with patch("homeassistant.util.dt.utcnow", return_value=next_time):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()

    assert refresh_runs == [
        [
            TrackTemplateResult(template_2, None, True),
        ]
    ]

    info.async_remove()


async def test_track_same_state_simple_no_trigger(hass: HomeAssistant) -> None:
    """Test track_same_change with no trigger."""
    callback_runs = []
    period = timedelta(minutes=1)

    @ha.callback
    def callback_run_callback():
        callback_runs.append(1)

    async_track_same_state(
        hass,
        period,
        callback_run_callback,
        callback(lambda _, _2, to_s: to_s.state == "on"),
        entity_ids="light.Bowl",
    )

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(callback_runs) == 0

    # Change state on state machine
    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(callback_runs) == 0

    # change time to track and see if they trigger
    future = dt_util.utcnow() + period
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert len(callback_runs) == 0


async def test_track_same_state_simple_trigger_check_funct(hass: HomeAssistant) -> None:
    """Test track_same_change with trigger and check funct."""
    callback_runs = []
    check_func = []
    period = timedelta(minutes=1)

    @ha.callback
    def callback_run_callback():
        callback_runs.append(1)

    @ha.callback
    def async_check_func(entity, from_s, to_s):
        check_func.append((entity, from_s, to_s))
        return True

    async_track_same_state(
        hass,
        period,
        callback_run_callback,
        entity_ids="light.Bowl",
        async_check_same_func=async_check_func,
    )

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(callback_runs) == 0
    assert check_func[-1][2].state == "on"
    assert check_func[-1][0] == "light.bowl"

    # change time to track and see if they trigger
    future = dt_util.utcnow() + period
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert len(callback_runs) == 1


async def test_track_time_interval(hass: HomeAssistant) -> None:
    """Test tracking time interval."""
    specific_runs = []

    utc_now = dt_util.utcnow()
    unsub = async_track_time_interval(
        hass, callback(lambda x: specific_runs.append(x)), timedelta(seconds=10)
    )

    async_fire_time_changed(hass, utc_now + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    async_fire_time_changed(hass, utc_now + timedelta(seconds=13))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(hass, utc_now + timedelta(minutes=20))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    unsub()

    async_fire_time_changed(hass, utc_now + timedelta(seconds=30))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2


async def test_track_time_interval_name(hass: HomeAssistant) -> None:
    """Test tracking time interval name.

    This test is to ensure that when a name is passed to async_track_time_interval,
    that the name can be found in the TimerHandle when stringified.
    """
    specific_runs = []
    unique_string = "xZ13"
    unsub = async_track_time_interval(
        hass,
        callback(lambda x: specific_runs.append(x)),
        timedelta(seconds=10),
        name=unique_string,
    )
    scheduled = getattr(hass.loop, "_scheduled")
    assert any(handle for handle in scheduled if unique_string in str(handle))
    unsub()

    assert all(handle for handle in scheduled if unique_string not in str(handle))
    await hass.async_block_till_done()


async def test_track_sunrise(hass: HomeAssistant) -> None:
    """Test track the sunrise."""
    latitude = 32.87336
    longitude = 117.22743

    # Setup sun component
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    location = LocationInfo(
        latitude=hass.config.latitude, longitude=hass.config.longitude
    )

    # Get next sunrise/sunset
    utc_now = datetime(2014, 5, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    utc_today = utc_now.date()

    mod = -1
    while True:
        next_rising = astral.sun.sunrise(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_rising > utc_now:
            break
        mod += 1

    # Track sunrise
    runs = []
    with freeze_time(utc_now):
        unsub = async_track_sunrise(hass, callback(lambda: runs.append(1)))

    offset_runs = []
    offset = timedelta(minutes=30)
    with freeze_time(utc_now):
        unsub2 = async_track_sunrise(
            hass, callback(lambda: offset_runs.append(1)), offset
        )

    # run tests
    with freeze_time(next_rising - offset):
        async_fire_time_changed(hass, next_rising - offset)
        await hass.async_block_till_done()
        assert len(runs) == 0
        assert len(offset_runs) == 0

    with freeze_time(next_rising):
        async_fire_time_changed(hass, next_rising)
        await hass.async_block_till_done()
        assert len(runs) == 1
        assert len(offset_runs) == 0

    with freeze_time(next_rising + offset):
        async_fire_time_changed(hass, next_rising + offset)
        await hass.async_block_till_done()
        assert len(runs) == 1
        assert len(offset_runs) == 1

    unsub()
    unsub2()

    with freeze_time(next_rising + offset):
        async_fire_time_changed(hass, next_rising + offset)
        await hass.async_block_till_done()
        assert len(runs) == 1
        assert len(offset_runs) == 1


async def test_track_sunrise_update_location(hass: HomeAssistant) -> None:
    """Test track the sunrise."""
    # Setup sun component
    hass.config.latitude = 32.87336
    hass.config.longitude = 117.22743

    location = LocationInfo(
        latitude=hass.config.latitude, longitude=hass.config.longitude
    )

    # Get next sunrise
    utc_now = datetime(2014, 5, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    utc_today = utc_now.date()

    mod = -1
    while True:
        next_rising = astral.sun.sunrise(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_rising > utc_now:
            break
        mod += 1

    # Track sunrise
    runs = []
    with freeze_time(utc_now):
        unsub = async_track_sunrise(hass, callback(lambda: runs.append(1)))

    # Mimic sunrise
    with freeze_time(next_rising):
        async_fire_time_changed(hass, next_rising)
        await hass.async_block_till_done()
        assert len(runs) == 1

    # Move!
    with freeze_time(utc_now):
        await hass.config.async_update(latitude=40.755931, longitude=-73.984606)
        await hass.async_block_till_done()

    # update location for astral
    location = LocationInfo(
        latitude=hass.config.latitude, longitude=hass.config.longitude
    )

    # Mimic sunrise
    with freeze_time(next_rising):
        async_fire_time_changed(hass, next_rising)
        await hass.async_block_till_done()
        # Did not increase
        assert len(runs) == 1

    # Get next sunrise
    mod = -1
    while True:
        next_rising = astral.sun.sunrise(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_rising > utc_now:
            break
        mod += 1

    with freeze_time(next_rising):
        # Mimic sunrise at new location
        async_fire_time_changed(hass, next_rising)
        await hass.async_block_till_done()
        assert len(runs) == 2

    unsub()


async def test_track_sunset(hass: HomeAssistant) -> None:
    """Test track the sunset."""
    latitude = 32.87336
    longitude = 117.22743

    location = LocationInfo(latitude=latitude, longitude=longitude)

    # Setup sun component
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    # Get next sunrise/sunset
    utc_now = datetime(2014, 5, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    utc_today = utc_now.date()

    mod = -1
    while True:
        next_setting = astral.sun.sunset(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_setting > utc_now:
            break
        mod += 1

    # Track sunset
    runs = []
    with freeze_time(utc_now):
        unsub = async_track_sunset(hass, callback(lambda: runs.append(1)))

    offset_runs = []
    offset = timedelta(minutes=30)
    with freeze_time(utc_now):
        unsub2 = async_track_sunset(
            hass, callback(lambda: offset_runs.append(1)), offset
        )

    # Run tests
    with freeze_time(next_setting - offset):
        async_fire_time_changed(hass, next_setting - offset)
        await hass.async_block_till_done()
        assert len(runs) == 0
        assert len(offset_runs) == 0

    with freeze_time(next_setting):
        async_fire_time_changed(hass, next_setting)
        await hass.async_block_till_done()
        assert len(runs) == 1
        assert len(offset_runs) == 0

    with freeze_time(next_setting + offset):
        async_fire_time_changed(hass, next_setting + offset)
        await hass.async_block_till_done()
        assert len(runs) == 1
        assert len(offset_runs) == 1

    unsub()
    unsub2()

    with freeze_time(next_setting + offset):
        async_fire_time_changed(hass, next_setting + offset)
        await hass.async_block_till_done()
        assert len(runs) == 1
        assert len(offset_runs) == 1


async def test_async_track_time_change(hass: HomeAssistant) -> None:
    """Test tracking time change."""
    none_runs = []
    wildcard_runs = []
    specific_runs = []

    now = dt_util.utcnow()

    time_that_will_not_match_right_away = datetime(
        now.year + 1, 5, 24, 11, 59, 55, tzinfo=dt_util.UTC
    )

    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        unsub = async_track_time_change(hass, callback(lambda x: none_runs.append(x)))
        unsub_utc = async_track_utc_time_change(
            hass, callback(lambda x: specific_runs.append(x)), second=[0, 30]
        )
        unsub_wildcard = async_track_time_change(
            hass,
            callback(lambda x: wildcard_runs.append(x)),
            second="*",
            minute="*",
            hour="*",
        )

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 12, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1
    assert len(none_runs) == 1

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 12, 0, 15, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 2
    assert len(none_runs) == 2

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 12, 0, 30, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 3
    assert len(none_runs) == 3

    unsub()
    unsub_utc()
    unsub_wildcard()

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 12, 0, 30, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 3
    assert len(none_runs) == 3


async def test_periodic_task_minute(hass: HomeAssistant) -> None:
    """Test periodic tasks per minute."""
    specific_runs = []

    now = dt_util.utcnow()

    time_that_will_not_match_right_away = datetime(
        now.year + 1, 5, 24, 11, 59, 55, tzinfo=dt_util.UTC
    )

    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        unsub = async_track_utc_time_change(
            hass, callback(lambda x: specific_runs.append(x)), minute="/5", second=0
        )

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 12, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 12, 3, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 12, 5, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    unsub()

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 12, 5, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 2


async def test_periodic_task_hour(hass: HomeAssistant) -> None:
    """Test periodic tasks per hour."""
    specific_runs = []

    now = dt_util.utcnow()

    time_that_will_not_match_right_away = datetime(
        now.year + 1, 5, 24, 21, 59, 55, tzinfo=dt_util.UTC
    )

    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        unsub = async_track_utc_time_change(
            hass,
            callback(lambda x: specific_runs.append(x)),
            hour="/2",
            minute=0,
            second=0,
        )

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 22, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 23, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 25, 0, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 25, 1, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 25, 2, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 3

    unsub()

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 25, 2, 0, 0, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 3


async def test_periodic_task_wrong_input(hass: HomeAssistant) -> None:
    """Test periodic tasks with wrong input."""
    specific_runs = []

    now = dt_util.utcnow()

    with pytest.raises(ValueError):
        async_track_utc_time_change(
            hass, callback(lambda x: specific_runs.append(x)), hour="/two"
        )

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 2, 0, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 0


async def test_periodic_task_clock_rollback(hass: HomeAssistant) -> None:
    """Test periodic tasks with the time rolling backwards."""
    specific_runs = []

    now = dt_util.utcnow()

    time_that_will_not_match_right_away = datetime(
        now.year + 1, 5, 24, 21, 59, 55, tzinfo=dt_util.UTC
    )

    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        unsub = async_track_utc_time_change(
            hass,
            callback(lambda x: specific_runs.append(x)),
            hour="/2",
            minute=0,
            second=0,
        )

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 22, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 23, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass,
        datetime(now.year + 1, 5, 24, 22, 0, 0, 999999, tzinfo=dt_util.UTC),
        fire_all=True,
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass,
        datetime(now.year + 1, 5, 24, 0, 0, 0, 999999, tzinfo=dt_util.UTC),
        fire_all=True,
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 25, 2, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    unsub()

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 25, 2, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 2


async def test_periodic_task_duplicate_time(hass: HomeAssistant) -> None:
    """Test periodic tasks not triggering on duplicate time."""
    specific_runs = []

    now = dt_util.utcnow()

    time_that_will_not_match_right_away = datetime(
        now.year + 1, 5, 24, 21, 59, 55, tzinfo=dt_util.UTC
    )

    with patch(
        "homeassistant.util.dt.utcnow", return_value=time_that_will_not_match_right_away
    ):
        unsub = async_track_utc_time_change(
            hass,
            callback(lambda x: specific_runs.append(x)),
            hour="/2",
            minute=0,
            second=0,
        )

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 22, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 24, 22, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    async_fire_time_changed(
        hass, datetime(now.year + 1, 5, 25, 0, 0, 0, 999999, tzinfo=dt_util.UTC)
    )
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    unsub()


# DST starts early morning March 28th 2021
@pytest.mark.freeze_time("2021-03-28 01:28:00+01:00")
async def test_periodic_task_entering_dst(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test periodic task behavior when entering dst."""
    hass.config.set_time_zone("Europe/Vienna")
    specific_runs = []

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # Make sure we enter DST during the test
    now_local = dt_util.now()
    assert now_local.utcoffset() != (now_local + timedelta(hours=2)).utcoffset()

    unsub = async_track_time_change(
        hass,
        callback(lambda x: specific_runs.append(x)),
        hour=2,
        minute=30,
        second=0,
    )

    freezer.move_to(f"{today} 01:50:00.999999+01:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    # There was no 02:30 today, the event should not fire until tomorrow
    freezer.move_to(f"{today} 03:50:00.999999+02:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    freezer.move_to(f"{tomorrow} 01:50:00.999999+02:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    freezer.move_to(f"{tomorrow} 02:50:00.999999+02:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    unsub()


# DST starts early morning March 28th 2021
@pytest.mark.freeze_time("2021-03-28 01:59:59+01:00")
async def test_periodic_task_entering_dst_2(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test periodic task behavior when entering dst.

    This tests a task firing every second in the range 0..58 (not *:*:59)
    """
    hass.config.set_time_zone("Europe/Vienna")
    specific_runs = []

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # Make sure we enter DST during the test
    now_local = dt_util.now()
    assert now_local.utcoffset() != (now_local + timedelta(hours=2)).utcoffset()

    unsub = async_track_time_change(
        hass,
        callback(lambda x: specific_runs.append(x)),
        second=list(range(59)),
    )

    freezer.move_to(f"{today} 01:59:59.999999+01:00")
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    freezer.move_to(f"{today} 03:00:00.999999+02:00")
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    freezer.move_to(f"{today} 03:00:01.999999+02:00")
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    freezer.move_to(f"{tomorrow} 01:59:59.999999+02:00")
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert len(specific_runs) == 3

    freezer.move_to(f"{tomorrow} 02:00:00.999999+02:00")
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert len(specific_runs) == 4

    unsub()


# DST ends early morning October 31st 2021
@pytest.mark.freeze_time("2021-10-31 02:28:00+02:00")
async def test_periodic_task_leaving_dst(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test periodic task behavior when leaving dst."""
    hass.config.set_time_zone("Europe/Vienna")
    specific_runs = []

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # Make sure we leave DST during the test
    now_local = dt_util.now()
    assert now_local.utcoffset() != (now_local + timedelta(hours=1)).utcoffset()

    unsub = async_track_time_change(
        hass,
        callback(lambda x: specific_runs.append(x)),
        hour=2,
        minute=30,
        second=0,
    )

    # The task should not fire yet
    freezer.move_to(f"{today} 02:28:00.999999+02:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 0
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    # The task should fire
    freezer.move_to(f"{today} 02:30:00.999999+02:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 0
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    # The task should not fire again
    freezer.move_to(f"{today} 02:55:00.999999+02:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 0
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    # DST has ended, the task should not fire yet
    freezer.move_to(f"{today} 02:15:00.999999+01:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 1  # DST has ended
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    # The task should fire
    freezer.move_to(f"{today} 02:45:00.999999+01:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 1
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    # The task should not fire again
    freezer.move_to(f"{today} 02:55:00.999999+01:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 1
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    # The task should fire again the next day
    freezer.move_to(f"{tomorrow} 02:55:00.999999+01:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 0
    await hass.async_block_till_done()
    assert len(specific_runs) == 3

    unsub()


# DST ends early morning October 31st 2021
@pytest.mark.freeze_time("2021-10-31 02:28:00+02:00")
async def test_periodic_task_leaving_dst_2(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test periodic task behavior when leaving dst."""
    hass.config.set_time_zone("Europe/Vienna")
    specific_runs = []

    today = date.today().isoformat()

    # Make sure we leave DST during the test
    now_local = dt_util.now()
    assert now_local.utcoffset() != (now_local + timedelta(hours=1)).utcoffset()

    unsub = async_track_time_change(
        hass,
        callback(lambda x: specific_runs.append(x)),
        minute=30,
        second=0,
    )

    # The task should not fire yet
    freezer.move_to(f"{today} 02:28:00.999999+02:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 0
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    # The task should fire
    freezer.move_to(f"{today} 02:55:00.999999+02:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 0
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    # DST has ended, the task should not fire yet
    freezer.move_to(f"{today} 02:15:00.999999+01:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 1
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    # The task should fire
    freezer.move_to(f"{today} 02:45:00.999999+01:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 1
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    # The task should not fire again
    freezer.move_to(f"{today} 02:55:00.999999+01:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 1
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    # The task should fire again the next hour
    freezer.move_to(f"{today} 03:55:00.999999+01:00")
    async_fire_time_changed(hass)
    assert dt_util.now().fold == 0
    await hass.async_block_till_done()
    assert len(specific_runs) == 3

    unsub()


async def test_call_later(hass: HomeAssistant) -> None:
    """Test calling an action later."""
    future = asyncio.get_running_loop().create_future()
    delay = 5
    delay_tolerance = 0.1
    schedule_utctime = dt_util.utcnow()

    @callback
    def action(__utcnow: datetime):
        _current_delay = __utcnow.timestamp() - schedule_utctime.timestamp()
        future.set_result(delay < _current_delay < (delay + delay_tolerance))

    async_call_later(hass, delay, action)

    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=delay))

    async with asyncio.timeout(delay + delay_tolerance):
        assert await future, "callback was called but the delay was wrong"


async def test_async_call_later(hass: HomeAssistant) -> None:
    """Test calling an action later."""
    future = asyncio.get_running_loop().create_future()
    delay = 5
    delay_tolerance = 0.1
    schedule_utctime = dt_util.utcnow()

    @callback
    def action(__utcnow: datetime):
        _current_delay = __utcnow.timestamp() - schedule_utctime.timestamp()
        future.set_result(delay < _current_delay < (delay + delay_tolerance))

    remove = async_call_later(hass, delay, action)

    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=delay))

    async with asyncio.timeout(delay + delay_tolerance):
        assert await future, "callback was called but the delay was wrong"
    assert isinstance(remove, Callable)
    remove()


async def test_async_call_later_timedelta(hass: HomeAssistant) -> None:
    """Test calling an action later with a timedelta."""
    future = asyncio.get_running_loop().create_future()
    delay = 5
    delay_tolerance = 0.1
    schedule_utctime = dt_util.utcnow()

    @callback
    def action(__utcnow: datetime):
        _current_delay = __utcnow.timestamp() - schedule_utctime.timestamp()
        future.set_result(delay < _current_delay < (delay + delay_tolerance))

    remove = async_call_later(hass, timedelta(seconds=delay), action)

    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=delay))

    async with asyncio.timeout(delay + delay_tolerance):
        assert await future, "callback was called but the delay was wrong"
    assert isinstance(remove, Callable)
    remove()


async def test_async_call_later_cancel(hass: HomeAssistant) -> None:
    """Test canceling a call_later action."""
    future = asyncio.get_running_loop().create_future()
    delay = 0.25
    delay_tolerance = 0.1

    @callback
    def action(__now: datetime):
        future.set_result(False)

    remove = async_call_later(hass, delay, action)
    # fast forward time a bit..
    async_fire_time_changed_exact(
        hass, dt_util.utcnow() + timedelta(seconds=delay - delay_tolerance)
    )
    # and remove before firing
    remove()
    # fast forward time beyond scheduled
    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=delay))

    with contextlib.suppress(asyncio.TimeoutError):
        async with asyncio.timeout(delay + delay_tolerance):
            assert await future, "callback not canceled"


async def test_track_state_change_event_chain_multple_entity(
    hass: HomeAssistant,
) -> None:
    """Test that adding a new state tracker inside a tracker does not fire right away."""
    tracker_called = []
    chained_tracker_called = []

    chained_tracker_unsub = []
    tracker_unsub = []

    @ha.callback
    def chained_single_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        chained_tracker_called.append((old_state, new_state))

    @ha.callback
    def single_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        tracker_called.append((old_state, new_state))

        chained_tracker_unsub.append(
            async_track_state_change_event(
                hass, ["light.bowl", "light.top"], chained_single_run_callback
            )
        )

    tracker_unsub.append(
        async_track_state_change_event(
            hass, ["light.bowl", "light.top"], single_run_callback
        )
    )

    hass.states.async_set("light.bowl", "on")
    hass.states.async_set("light.top", "on")
    await hass.async_block_till_done()

    assert len(tracker_called) == 2
    assert len(chained_tracker_called) == 1
    assert len(tracker_unsub) == 1
    assert len(chained_tracker_unsub) == 2

    hass.states.async_set("light.bowl", "off")
    await hass.async_block_till_done()

    assert len(tracker_called) == 3
    assert len(chained_tracker_called) == 3
    assert len(tracker_unsub) == 1
    assert len(chained_tracker_unsub) == 3


async def test_track_state_change_event_chain_single_entity(
    hass: HomeAssistant,
) -> None:
    """Test that adding a new state tracker inside a tracker does not fire right away."""
    tracker_called = []
    chained_tracker_called = []

    chained_tracker_unsub = []
    tracker_unsub = []

    @ha.callback
    def chained_single_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        chained_tracker_called.append((old_state, new_state))

    @ha.callback
    def single_run_callback(event: EventType[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        tracker_called.append((old_state, new_state))

        chained_tracker_unsub.append(
            async_track_state_change_event(
                hass, "light.bowl", chained_single_run_callback
            )
        )

    tracker_unsub.append(
        async_track_state_change_event(hass, "light.bowl", single_run_callback)
    )

    hass.states.async_set("light.bowl", "on")
    await hass.async_block_till_done()

    assert len(tracker_called) == 1
    assert len(chained_tracker_called) == 0
    assert len(tracker_unsub) == 1
    assert len(chained_tracker_unsub) == 1

    hass.states.async_set("light.bowl", "off")
    await hass.async_block_till_done()

    assert len(tracker_called) == 2
    assert len(chained_tracker_called) == 1
    assert len(tracker_unsub) == 1
    assert len(chained_tracker_unsub) == 2


async def test_track_point_in_utc_time_cancel(hass: HomeAssistant) -> None:
    """Test cancel of async track point in time."""

    times = []

    @ha.callback
    def run_callback(utc_time):
        nonlocal times
        times.append(utc_time)

    def _setup_listeners():
        """Ensure we test the non-async version."""
        utc_now = dt_util.utcnow()

        with pytest.raises(TypeError):
            track_point_in_utc_time("nothass", run_callback, utc_now)

        unsub1 = track_point_in_utc_time(
            hass, run_callback, utc_now + timedelta(seconds=0.1)
        )
        track_point_in_utc_time(hass, run_callback, utc_now + timedelta(seconds=0.1))

        unsub1()

    await hass.async_add_executor_job(_setup_listeners)

    await asyncio.sleep(0.2)

    assert len(times) == 1
    assert times[0].tzinfo == dt_util.UTC


async def test_async_track_point_in_time_cancel(hass: HomeAssistant) -> None:
    """Test cancel of async track point in time."""

    times = []
    hass.config.set_time_zone("US/Hawaii")
    hst_tz = dt_util.get_time_zone("US/Hawaii")

    @ha.callback
    def run_callback(local_time):
        nonlocal times
        times.append(local_time)

    utc_now = dt_util.utcnow()
    hst_now = utc_now.astimezone(hst_tz)

    unsub1 = async_track_point_in_time(
        hass, run_callback, hst_now + timedelta(seconds=0.1)
    )
    async_track_point_in_time(hass, run_callback, hst_now + timedelta(seconds=0.1))

    unsub1()

    await asyncio.sleep(0.2)

    assert len(times) == 1
    assert "US/Hawaii" in str(times[0].tzinfo)


async def test_async_track_entity_registry_updated_event(hass: HomeAssistant) -> None:
    """Test tracking entity registry updates for an entity_id."""

    entity_id = "switch.puppy_feeder"
    new_entity_id = "switch.dog_feeder"
    untracked_entity_id = "switch.kitty_feeder"

    hass.states.async_set(entity_id, "on")
    await hass.async_block_till_done()
    event_data = []

    @ha.callback
    def run_callback(event):
        event_data.append(event.data)

    unsub1 = async_track_entity_registry_updated_event(hass, entity_id, run_callback)
    unsub2 = async_track_entity_registry_updated_event(
        hass, new_entity_id, run_callback
    )
    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "entity_id": entity_id}
    )
    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "create", "entity_id": untracked_entity_id},
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED,
        {
            "action": "update",
            "entity_id": new_entity_id,
            "old_entity_id": entity_id,
            "changes": {},
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": new_entity_id}
    )
    await hass.async_block_till_done()

    unsub1()
    unsub2()
    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "entity_id": entity_id}
    )
    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "entity_id": new_entity_id}
    )
    await hass.async_block_till_done()

    assert event_data[0] == {"action": "create", "entity_id": "switch.puppy_feeder"}
    assert event_data[1] == {
        "action": "update",
        "changes": {},
        "entity_id": "switch.dog_feeder",
        "old_entity_id": "switch.puppy_feeder",
    }
    assert event_data[2] == {"action": "remove", "entity_id": "switch.dog_feeder"}


async def test_async_track_entity_registry_updated_event_with_a_callback_that_throws(
    hass: HomeAssistant,
) -> None:
    """Test tracking entity registry updates for an entity_id when one callback throws."""

    entity_id = "switch.puppy_feeder"

    hass.states.async_set(entity_id, "on")
    await hass.async_block_till_done()
    event_data = []

    @ha.callback
    def run_callback(event):
        event_data.append(event.data)

    @ha.callback
    def failing_callback(event):
        raise ValueError

    unsub1 = async_track_entity_registry_updated_event(
        hass, entity_id, failing_callback
    )
    unsub2 = async_track_entity_registry_updated_event(hass, entity_id, run_callback)
    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "entity_id": entity_id}
    )
    await hass.async_block_till_done()
    unsub1()
    unsub2()

    assert event_data[0] == {"action": "create", "entity_id": "switch.puppy_feeder"}


async def test_async_track_entity_registry_updated_event_with_empty_list(
    hass: HomeAssistant,
) -> None:
    """Test async_track_entity_registry_updated_event passing an empty list of entities."""
    unsub_single = async_track_entity_registry_updated_event(
        hass, [], ha.callback(lambda event: None)
    )
    unsub_single2 = async_track_entity_registry_updated_event(
        hass, [], ha.callback(lambda event: None)
    )

    unsub_single2()
    unsub_single()


async def test_async_track_device_registry_updated_event(hass: HomeAssistant) -> None:
    """Test tracking device registry updates for an device_id."""

    device_id = "b92c0f06fbc911edacc9eea8ae14f866"
    device_id2 = "747bbf22fbca11ed843aeea8ae14f866"
    untracked_device_id = "bda93f86fbc911edacc9eea8ae14f866"

    single_event_data = []
    multiple_event_data = []

    @ha.callback
    def single_device_id_callback(event: ha.Event) -> None:
        single_event_data.append(event.data)

    @ha.callback
    def multiple_device_id_callback(event: ha.Event) -> None:
        multiple_event_data.append(event.data)

    unsub1 = async_track_device_registry_updated_event(
        hass, device_id, single_device_id_callback
    )
    unsub2 = async_track_device_registry_updated_event(
        hass, [device_id, device_id2], multiple_device_id_callback
    )
    hass.bus.async_fire(
        EVENT_DEVICE_REGISTRY_UPDATED, {"action": "create", "device_id": device_id}
    )
    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "create", "device_id": untracked_device_id},
    )
    await hass.async_block_till_done()
    assert len(single_event_data) == 1
    assert len(multiple_event_data) == 1
    hass.bus.async_fire(
        EVENT_DEVICE_REGISTRY_UPDATED, {"action": "create", "device_id": device_id2}
    )
    await hass.async_block_till_done()
    assert len(single_event_data) == 1
    assert len(multiple_event_data) == 2

    unsub1()
    unsub2()
    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "device_id": device_id}
    )
    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "device_id": device_id2}
    )
    await hass.async_block_till_done()
    assert len(single_event_data) == 1
    assert len(multiple_event_data) == 2


async def test_async_track_device_registry_updated_event_with_empty_list(
    hass: HomeAssistant,
) -> None:
    """Test async_track_device_registry_updated_event passing an empty list of devices."""
    unsub_single = async_track_device_registry_updated_event(
        hass, [], ha.callback(lambda event: None)
    )
    unsub_single2 = async_track_device_registry_updated_event(
        hass, [], ha.callback(lambda event: None)
    )

    unsub_single2()
    unsub_single()


async def test_async_track_device_registry_updated_event_with_a_callback_that_throws(
    hass: HomeAssistant,
) -> None:
    """Test tracking device registry updates for an device when one callback throws."""

    device_id = "b92c0f06fbc911edacc9eea8ae14f866"

    event_data = []

    @ha.callback
    def run_callback(event: ha.Event) -> None:
        event_data.append(event.data)

    @ha.callback
    def failing_callback(event: ha.Event) -> None:
        raise ValueError

    unsub1 = async_track_device_registry_updated_event(
        hass, device_id, failing_callback
    )
    unsub2 = async_track_device_registry_updated_event(hass, device_id, run_callback)
    hass.bus.async_fire(
        EVENT_DEVICE_REGISTRY_UPDATED, {"action": "create", "device_id": device_id}
    )
    await hass.async_block_till_done()
    unsub1()
    unsub2()

    assert event_data[0] == {"action": "create", "device_id": device_id}
