"""Support to turn on lights based on the states."""

from datetime import timedelta
from functools import partial
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DOMAIN_DEVICE_TRACKER,
    is_on as device_tracker_is_on,
)
from homeassistant.components.group import get_entity_ids as group_get_entity_ids
from homeassistant.components.light import (
    ATTR_PROFILE,
    ATTR_TRANSITION,
    DOMAIN as DOMAIN_LIGHT,
    is_on as light_is_on,
)
from homeassistant.components.person import DOMAIN as DOMAIN_PERSON
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_HOME,
    STATE_NOT_HOME,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.sun import get_astral_event_next, is_up
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

DOMAIN = "device_sun_light_trigger"
CONF_DEVICE_GROUP = "device_group"
CONF_DISABLE_TURN_OFF = "disable_turn_off"
CONF_LIGHT_GROUP = "light_group"
CONF_LIGHT_PROFILE = "light_profile"

DEFAULT_DISABLE_TURN_OFF = False
DEFAULT_LIGHT_PROFILE = "relax"

LIGHT_TRANSITION_TIME = timedelta(minutes=15)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DEVICE_GROUP): cv.entity_id,
                vol.Optional(
                    CONF_DISABLE_TURN_OFF, default=DEFAULT_DISABLE_TURN_OFF
                ): cv.boolean,
                vol.Optional(CONF_LIGHT_GROUP): cv.string,
                vol.Optional(
                    CONF_LIGHT_PROFILE, default=DEFAULT_LIGHT_PROFILE
                ): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the triggers to control lights based on device presence."""
    conf = config[DOMAIN]
    disable_turn_off = conf[CONF_DISABLE_TURN_OFF]
    light_group = conf.get(CONF_LIGHT_GROUP)
    light_profile = conf[CONF_LIGHT_PROFILE]
    device_group = conf.get(CONF_DEVICE_GROUP)

    async def activate_on_start(_):
        """Activate automation."""
        await activate_automation(
            hass, device_group, light_group, light_profile, disable_turn_off
        )

    if hass.is_running:
        await activate_on_start(None)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, activate_on_start)

    return True


async def activate_automation(  # noqa: C901
    hass, device_group, light_group, light_profile, disable_turn_off
):
    """Activate the automation."""
    logger = logging.getLogger(__name__)

    if device_group is None:
        device_entity_ids = hass.states.async_entity_ids(DOMAIN_DEVICE_TRACKER)
    else:
        device_entity_ids = group_get_entity_ids(
            hass, device_group, DOMAIN_DEVICE_TRACKER
        )
        device_entity_ids.extend(
            group_get_entity_ids(hass, device_group, DOMAIN_PERSON)
        )

    if not device_entity_ids:
        logger.error("No devices found to track")
        return

    # Get the light IDs from the specified group
    if light_group is None:
        light_ids = hass.states.async_entity_ids(DOMAIN_LIGHT)
    else:
        light_ids = group_get_entity_ids(hass, light_group, DOMAIN_LIGHT)

    if not light_ids:
        logger.error("No lights found to turn on")
        return

    @callback
    def anyone_home():
        """Test if anyone is home."""
        return any(device_tracker_is_on(hass, dt_id) for dt_id in device_entity_ids)

    @callback
    def any_light_on():
        """Test if any light on."""
        return any(light_is_on(hass, light_id) for light_id in light_ids)

    def calc_time_for_light_when_sunset():
        """Calculate the time when to start fading lights in when sun sets.

        Returns None if no next_setting data available.

        Async friendly.
        """
        next_setting = get_astral_event_next(hass, SUN_EVENT_SUNSET)
        if not next_setting:
            return None
        return next_setting - LIGHT_TRANSITION_TIME * len(light_ids)

    async def async_turn_on_before_sunset(light_id):
        """Turn on lights."""
        if not anyone_home() or light_is_on(hass, light_id):
            return
        await hass.services.async_call(
            DOMAIN_LIGHT,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: light_id,
                ATTR_TRANSITION: LIGHT_TRANSITION_TIME.total_seconds(),
                ATTR_PROFILE: light_profile,
            },
        )

    @callback
    def async_turn_on_factory(light_id):
        """Generate turn on callbacks as factory."""

        async def async_turn_on_light(now):
            """Turn on specific light."""
            await async_turn_on_before_sunset(light_id)

        return async_turn_on_light

    # Track every time sun rises so we can schedule a time-based
    # pre-sun set event
    @callback
    def schedule_light_turn_on(now):
        """Turn on all the lights at the moment sun sets.

        We will schedule to have each light start after one another
        and slowly transition in.
        """
        start_point = calc_time_for_light_when_sunset()
        if not start_point:
            return

        for index, light_id in enumerate(light_ids):
            async_track_point_in_utc_time(
                hass,
                async_turn_on_factory(light_id),
                start_point + index * LIGHT_TRANSITION_TIME,
            )

    async_track_point_in_utc_time(
        hass, schedule_light_turn_on, get_astral_event_next(hass, SUN_EVENT_SUNRISE)
    )

    # If the sun is already above horizon schedule the time-based pre-sun set
    # event.
    if is_up(hass):
        schedule_light_turn_on(None)

    @callback
    def check_light_on_dev_state_change(
        from_state: str, to_state: str, event: Event[EventStateChangedData]
    ) -> None:
        """Handle tracked device state changes."""
        event_data = event.data
        if (
            (old_state := event_data["old_state"]) is None
            or (new_state := event_data["new_state"]) is None
            or old_state.state != from_state
            or new_state.state != to_state
        ):
            return

        entity = event_data["entity_id"]
        lights_are_on = any_light_on()
        light_needed = not (lights_are_on or is_up(hass))

        # These variables are needed for the elif check
        now = dt_util.utcnow()
        start_point = calc_time_for_light_when_sunset()

        # Do we need lights?
        if light_needed:
            logger.info("Home coming event for %s. Turning lights on", entity)
            hass.async_create_task(
                hass.services.async_call(
                    DOMAIN_LIGHT,
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: light_ids, ATTR_PROFILE: light_profile},
                )
            )

        # Are we in the time span were we would turn on the lights
        # if someone would be home?
        # Check this by seeing if current time is later then the point
        # in time when we would start putting the lights on.
        elif start_point and start_point < now < get_astral_event_next(
            hass, SUN_EVENT_SUNSET
        ):
            # Check for every light if it would be on if someone was home
            # when the fading in started and turn it on if so
            for index, light_id in enumerate(light_ids):
                if now > start_point + index * LIGHT_TRANSITION_TIME:
                    hass.async_create_task(
                        hass.services.async_call(
                            DOMAIN_LIGHT, SERVICE_TURN_ON, {ATTR_ENTITY_ID: light_id}
                        )
                    )

                else:
                    # If this light didn't happen to be turned on yet so
                    # will all the following then, break.
                    break

    async_track_state_change_event(
        hass,
        device_entity_ids,
        partial(check_light_on_dev_state_change, STATE_NOT_HOME, STATE_HOME),
    )

    if disable_turn_off:
        return

    @callback
    def turn_off_lights_when_all_leave(entity, old_state, new_state):
        """Handle device group state change."""
        # Make sure there is not someone home
        if anyone_home():
            return

        # Check if any light is on
        if not any_light_on():
            return

        logger.info("Everyone has left but there are lights on. Turning them off")
        hass.async_create_task(
            hass.services.async_call(
                DOMAIN_LIGHT, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: light_ids}
            )
        )

    async_track_state_change_event(
        hass,
        device_entity_ids,
        partial(turn_off_lights_when_all_leave, STATE_HOME, STATE_NOT_HOME),
    )

    return
