"""Offer time listening automation rules."""

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
from typing import NamedTuple

import voluptuous as vol

from homeassistant.components import sensor
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_AT,
    CONF_ENTITY_ID,
    CONF_OFFSET,
    CONF_PLATFORM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HassJob,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

_TIME_TRIGGER_ENTITY = vol.All(str, cv.entity_domain(["input_datetime", "sensor"]))

_TIME_TRIGGER_ENTITY_WITH_OFFSET = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(["sensor"]),
        vol.Optional(CONF_OFFSET): cv.time_period,
    }
)

_TIME_TRIGGER_SCHEMA = vol.Any(
    cv.time,
    _TIME_TRIGGER_ENTITY,
    _TIME_TRIGGER_ENTITY_WITH_OFFSET,
    msg=(
        "Expected HH:MM, HH:MM:SS, an Entity ID with domain 'input_datetime' or "
        "'sensor', or a combination of a timestamp sensor entity and an offset."
    ),
)

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "time",
        vol.Required(CONF_AT): vol.All(cv.ensure_list, [_TIME_TRIGGER_SCHEMA]),
    }
)


class TrackEntity(NamedTuple):
    """Represents a tracking entity for a time trigger."""

    entity_id: str
    callback: Callable


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    entities: dict[tuple[str, timedelta], CALLBACK_TYPE] = {}
    removes: list[CALLBACK_TYPE] = []
    job = HassJob(action, f"time trigger {trigger_info}")

    @callback
    def time_automation_listener(
        description: str, now: datetime, *, entity_id: str | None = None
    ) -> None:
        """Listen for time changes and calls action."""
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": "time",
                    "now": now,
                    "description": description,
                    "entity_id": entity_id,
                }
            },
        )

    @callback
    def update_entity_trigger_event(
        event: Event[EventStateChangedData], offset: timedelta = timedelta(0)
    ) -> None:
        """update_entity_trigger from the event."""
        return update_entity_trigger(
            event.data["entity_id"], event.data["new_state"], offset
        )

    @callback
    def update_entity_trigger(
        entity_id: str, new_state: State | None = None, offset: timedelta = timedelta(0)
    ) -> None:
        """Update the entity trigger for the entity_id."""
        # If a listener was already set up for entity, remove it.
        if remove := entities.pop((entity_id, offset), None):
            remove()
            remove = None

        if not new_state:
            return

        trigger_dt: datetime | None

        # Check state of entity. If valid, set up a listener.
        if new_state.domain == "input_datetime":
            if has_date := new_state.attributes["has_date"]:
                year = new_state.attributes["year"]
                month = new_state.attributes["month"]
                day = new_state.attributes["day"]
            if has_time := new_state.attributes["has_time"]:
                hour = new_state.attributes["hour"]
                minute = new_state.attributes["minute"]
                second = new_state.attributes["second"]
            else:
                # If no time then use midnight.
                hour = minute = second = 0

            if has_date:
                # If input_datetime has date, then track point in time.
                trigger_dt = datetime(
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    second,
                    tzinfo=dt_util.get_default_time_zone(),
                )
                # Only set up listener if time is now or in the future.
                if trigger_dt >= dt_util.now():
                    remove = async_track_point_in_time(
                        hass,
                        partial(
                            time_automation_listener,
                            f"time set in {entity_id}",
                            entity_id=entity_id,
                        ),
                        trigger_dt,
                    )
            elif has_time:
                # Else if it has time, then track time change.
                remove = async_track_time_change(
                    hass,
                    partial(
                        time_automation_listener,
                        f"time set in {entity_id}",
                        entity_id=entity_id,
                    ),
                    hour=hour,
                    minute=minute,
                    second=second,
                )
        elif (
            new_state.domain == "sensor"
            and new_state.attributes.get(ATTR_DEVICE_CLASS)
            == sensor.SensorDeviceClass.TIMESTAMP
            and new_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            trigger_dt = dt_util.parse_datetime(new_state.state)

            if trigger_dt is not None:
                trigger_dt += offset

            if trigger_dt is not None and trigger_dt > dt_util.utcnow():
                remove = async_track_point_in_time(
                    hass,
                    partial(
                        time_automation_listener,
                        f"time set in {entity_id}",
                        entity_id=entity_id,
                    ),
                    trigger_dt,
                )

        # Was a listener set up?
        if remove:
            entities[(entity_id, offset)] = remove

    to_track: list[TrackEntity] = []

    for at_time in config[CONF_AT]:
        if isinstance(at_time, str):
            # entity
            update_entity_trigger(at_time, new_state=hass.states.get(at_time))
            to_track.append(TrackEntity(at_time, update_entity_trigger_event))
        elif isinstance(at_time, dict) and CONF_OFFSET in at_time:
            # entity with offset
            entity_id: str = at_time.get(CONF_ENTITY_ID, "")
            offset: timedelta = at_time.get(CONF_OFFSET, timedelta(0))
            update_entity_trigger(
                entity_id, new_state=hass.states.get(entity_id), offset=offset
            )
            to_track.append(
                TrackEntity(
                    entity_id, partial(update_entity_trigger_event, offset=offset)
                )
            )
        else:
            # datetime.time
            removes.append(
                async_track_time_change(
                    hass,
                    partial(time_automation_listener, "time"),
                    hour=at_time.hour,
                    minute=at_time.minute,
                    second=at_time.second,
                )
            )

    # Besides time, we also track state changes of requested entities.
    removes.extend(
        (async_track_state_change_event(hass, entry.entity_id, entry.callback))
        for entry in to_track
    )

    @callback
    def remove_track_time_changes() -> None:
        """Remove tracked time changes."""
        for remove in entities.values():
            remove()
        for remove in removes:
            remove()

    return remove_track_time_changes
