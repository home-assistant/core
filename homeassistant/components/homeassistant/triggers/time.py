"""Offer time listening automation rules."""
from datetime import datetime
from functools import partial

import voluptuous as vol

from homeassistant.const import CONF_AT, CONF_PLATFORM
from homeassistant.core import HassJob, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_change,
)
import homeassistant.util.dt as dt_util

# mypy: allow-untyped-defs, no-check-untyped-defs

_TIME_TRIGGER_SCHEMA = vol.Any(
    cv.time,
    vol.All(str, cv.entity_domain("input_datetime")),
    msg="Expected HH:MM, HH:MM:SS or Entity ID from domain 'input_datetime'",
)

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "time",
        vol.Required(CONF_AT): vol.All(cv.ensure_list, [_TIME_TRIGGER_SCHEMA]),
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    entities = {}
    removes = []
    job = HassJob(action)

    @callback
    def time_automation_listener(description, now, *, entity_id=None):
        """Listen for time changes and calls action."""
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    "platform": "time",
                    "now": now,
                    "description": description,
                    "entity_id": entity_id,
                }
            },
        )

    @callback
    def update_entity_trigger_event(event):
        """update_entity_trigger from the event."""
        return update_entity_trigger(event.data["entity_id"], event.data["new_state"])

    @callback
    def update_entity_trigger(entity_id, new_state=None):
        """Update the entity trigger for the entity_id."""
        # If a listener was already set up for entity, remove it.
        remove = entities.get(entity_id)
        if remove:
            remove()
            removes.remove(remove)
            remove = None

        # Check state of entity. If valid, set up a listener.
        if new_state:
            has_date = new_state.attributes["has_date"]
            if has_date:
                year = new_state.attributes["year"]
                month = new_state.attributes["month"]
                day = new_state.attributes["day"]
            has_time = new_state.attributes["has_time"]
            if has_time:
                hour = new_state.attributes["hour"]
                minute = new_state.attributes["minute"]
                second = new_state.attributes["second"]
            else:
                # If no time then use midnight.
                hour = minute = second = 0

            if has_date:
                # If input_datetime has date, then track point in time.
                trigger_dt = dt_util.DEFAULT_TIME_ZONE.localize(
                    datetime(year, month, day, hour, minute, second)
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

        # Was a listener set up?
        if remove:
            removes.append(remove)

        entities[entity_id] = remove

    for at_time in config[CONF_AT]:
        if isinstance(at_time, str):
            # input_datetime entity
            update_entity_trigger(at_time, new_state=hass.states.get(at_time))
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

    # Track state changes of any entities.
    removes.append(
        async_track_state_change_event(
            hass, list(entities), update_entity_trigger_event
        )
    )

    @callback
    def remove_track_time_changes():
        """Remove tracked time changes."""
        for remove in removes:
            remove()

    return remove_track_time_changes
