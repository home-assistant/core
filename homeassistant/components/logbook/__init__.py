"""Event parser and human readable log generator."""
from datetime import timedelta
from itertools import groupby
import logging
import time

from sqlalchemy.exc import SQLAlchemyError
import voluptuous as vol

from homeassistant.components import sun
from homeassistant.components.homekit.const import (
    ATTR_DISPLAY_NAME,
    ATTR_VALUE,
    DOMAIN as DOMAIN_HOMEKIT,
    EVENT_HOMEKIT_CHANGED,
)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder.models import Events, States
from homeassistant.components.recorder.util import (
    QUERY_RETRY_WAIT,
    RETRIES,
    session_scope,
)
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_HIDDEN,
    ATTR_NAME,
    ATTR_SERVICE,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    EVENT_AUTOMATION_TRIGGERED,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGBOOK_ENTRY,
    EVENT_SCRIPT_STARTED,
    EVENT_STATE_CHANGED,
    HTTP_BAD_REQUEST,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, State, callback, split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_MESSAGE = "message"

CONF_DOMAINS = "domains"
CONF_ENTITIES = "entities"
CONTINUOUS_DOMAINS = ["proximity", "sensor"]

DOMAIN = "logbook"

GROUP_BY_MINUTES = 15

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                CONF_EXCLUDE: vol.Schema(
                    {
                        vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                        vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }
                ),
                CONF_INCLUDE: vol.Schema(
                    {
                        vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                        vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

ALL_EVENT_TYPES = [
    EVENT_STATE_CHANGED,
    EVENT_LOGBOOK_ENTRY,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_HOMEKIT_CHANGED,
    EVENT_AUTOMATION_TRIGGERED,
    EVENT_SCRIPT_STARTED,
]

LOG_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_MESSAGE): cv.template,
        vol.Optional(ATTR_DOMAIN): cv.slug,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
    }
)


@bind_hass
def log_entry(hass, name, message, domain=None, entity_id=None):
    """Add an entry to the logbook."""
    hass.add_job(async_log_entry, hass, name, message, domain, entity_id)


@bind_hass
def async_log_entry(hass, name, message, domain=None, entity_id=None):
    """Add an entry to the logbook."""
    data = {ATTR_NAME: name, ATTR_MESSAGE: message}

    if domain is not None:
        data[ATTR_DOMAIN] = domain
    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id
    hass.bus.async_fire(EVENT_LOGBOOK_ENTRY, data)


@bind_hass
def async_describe_event(hass, domain, event_name, describe_callback):
    """Teach logbook how to describe a new event."""
    hass.data.setdefault(DOMAIN, {})[event_name] = (domain, describe_callback)


async def async_setup(hass, config):
    """Listen for download events to download files."""

    @callback
    def log_message(service):
        """Handle sending notification message service calls."""
        message = service.data[ATTR_MESSAGE]
        name = service.data[ATTR_NAME]
        domain = service.data.get(ATTR_DOMAIN)
        entity_id = service.data.get(ATTR_ENTITY_ID)

        message.hass = hass
        message = message.async_render()
        async_log_entry(hass, name, message, domain, entity_id)

    hass.http.register_view(LogbookView(config.get(DOMAIN, {})))

    hass.components.frontend.async_register_built_in_panel(
        "logbook", "logbook", "hass:format-list-bulleted-type"
    )

    hass.services.async_register(DOMAIN, "log", log_message, schema=LOG_MESSAGE_SCHEMA)
    return True


class LogbookView(HomeAssistantView):
    """Handle logbook view requests."""

    url = "/api/logbook"
    name = "api:logbook"
    extra_urls = ["/api/logbook/{datetime}"]

    def __init__(self, config):
        """Initialize the logbook view."""
        self.config = config

    async def get(self, request, datetime=None):
        """Retrieve logbook entries."""
        if datetime:
            datetime = dt_util.parse_datetime(datetime)

            if datetime is None:
                return self.json_message("Invalid datetime", HTTP_BAD_REQUEST)
        else:
            datetime = dt_util.start_of_local_day()

        period = request.query.get("period")
        if period is None:
            period = 1
        else:
            period = int(period)

        entity_id = request.query.get("entity")
        start_day = dt_util.as_utc(datetime) - timedelta(days=period - 1)
        end_day = start_day + timedelta(days=period)
        hass = request.app["hass"]

        def json_events():
            """Fetch events and generate JSON."""
            return self.json(
                _get_events(hass, self.config, start_day, end_day, entity_id)
            )

        return await hass.async_add_job(json_events)


def humanify(hass, events):
    """Generate a converted list of events into Entry objects.

    Will try to group events if possible:
    - if 2+ sensor updates in GROUP_BY_MINUTES, show last
    - if Home Assistant stop and start happen in same minute call it restarted
    """
    domain_prefixes = tuple(f"{dom}." for dom in CONTINUOUS_DOMAINS)

    # Group events in batches of GROUP_BY_MINUTES
    for _, g_events in groupby(
        events, lambda event: event.time_fired.minute // GROUP_BY_MINUTES
    ):

        events_batch = list(g_events)

        # Keep track of last sensor states
        last_sensor_event = {}

        # Group HA start/stop events
        # Maps minute of event to 1: stop, 2: stop + start
        start_stop_events = {}

        # Process events
        for event in events_batch:
            if event.event_type == EVENT_STATE_CHANGED:
                entity_id = event.data.get("entity_id")

                if entity_id.startswith(domain_prefixes):
                    last_sensor_event[entity_id] = event

            elif event.event_type == EVENT_HOMEASSISTANT_STOP:
                if event.time_fired.minute in start_stop_events:
                    continue

                start_stop_events[event.time_fired.minute] = 1

            elif event.event_type == EVENT_HOMEASSISTANT_START:
                if event.time_fired.minute not in start_stop_events:
                    continue

                start_stop_events[event.time_fired.minute] = 2

        # Yield entries
        external_events = hass.data.get(DOMAIN, {})
        for event in events_batch:
            if event.event_type in external_events:
                domain, describe_event = external_events[event.event_type]
                data = describe_event(event)
                data["when"] = event.time_fired
                data["domain"] = domain
                data["context_id"] = event.context.id
                data["context_user_id"] = event.context.user_id
                yield data

            if event.event_type == EVENT_STATE_CHANGED:
                to_state = State.from_dict(event.data.get("new_state"))

                domain = to_state.domain

                # Skip all but the last sensor state
                if (
                    domain in CONTINUOUS_DOMAINS
                    and event != last_sensor_event[to_state.entity_id]
                ):
                    continue

                # Don't show continuous sensor value changes in the logbook
                if domain in CONTINUOUS_DOMAINS and to_state.attributes.get(
                    "unit_of_measurement"
                ):
                    continue

                yield {
                    "when": event.time_fired,
                    "name": to_state.name,
                    "message": _entry_message_from_state(domain, to_state),
                    "domain": domain,
                    "entity_id": to_state.entity_id,
                    "context_id": event.context.id,
                    "context_user_id": event.context.user_id,
                }

            elif event.event_type == EVENT_HOMEASSISTANT_START:
                if start_stop_events.get(event.time_fired.minute) == 2:
                    continue

                yield {
                    "when": event.time_fired,
                    "name": "Home Assistant",
                    "message": "started",
                    "domain": HA_DOMAIN,
                    "context_id": event.context.id,
                    "context_user_id": event.context.user_id,
                }

            elif event.event_type == EVENT_HOMEASSISTANT_STOP:
                if start_stop_events.get(event.time_fired.minute) == 2:
                    action = "restarted"
                else:
                    action = "stopped"

                yield {
                    "when": event.time_fired,
                    "name": "Home Assistant",
                    "message": action,
                    "domain": HA_DOMAIN,
                    "context_id": event.context.id,
                    "context_user_id": event.context.user_id,
                }

            elif event.event_type == EVENT_LOGBOOK_ENTRY:
                domain = event.data.get(ATTR_DOMAIN)
                entity_id = event.data.get(ATTR_ENTITY_ID)
                if domain is None and entity_id is not None:
                    try:
                        domain = split_entity_id(str(entity_id))[0]
                    except IndexError:
                        pass

                yield {
                    "when": event.time_fired,
                    "name": event.data.get(ATTR_NAME),
                    "message": event.data.get(ATTR_MESSAGE),
                    "domain": domain,
                    "entity_id": entity_id,
                    "context_id": event.context.id,
                    "context_user_id": event.context.user_id,
                }

            elif event.event_type == EVENT_HOMEKIT_CHANGED:
                data = event.data
                entity_id = data.get(ATTR_ENTITY_ID)
                value = data.get(ATTR_VALUE)

                value_msg = f" to {value}" if value else ""
                message = f"send command {data[ATTR_SERVICE]}{value_msg} for {data[ATTR_DISPLAY_NAME]}"

                yield {
                    "when": event.time_fired,
                    "name": "HomeKit",
                    "message": message,
                    "domain": DOMAIN_HOMEKIT,
                    "entity_id": entity_id,
                    "context_id": event.context.id,
                    "context_user_id": event.context.user_id,
                }

            elif event.event_type == EVENT_AUTOMATION_TRIGGERED:
                yield {
                    "when": event.time_fired,
                    "name": event.data.get(ATTR_NAME),
                    "message": "has been triggered",
                    "domain": "automation",
                    "entity_id": event.data.get(ATTR_ENTITY_ID),
                    "context_id": event.context.id,
                    "context_user_id": event.context.user_id,
                }

            elif event.event_type == EVENT_SCRIPT_STARTED:
                yield {
                    "when": event.time_fired,
                    "name": event.data.get(ATTR_NAME),
                    "message": "started",
                    "domain": "script",
                    "entity_id": event.data.get(ATTR_ENTITY_ID),
                    "context_id": event.context.id,
                    "context_user_id": event.context.user_id,
                }


def _get_related_entity_ids(session, entity_filter):
    timer_start = time.perf_counter()

    query = session.query(States).with_entities(States.entity_id).distinct()

    for tryno in range(0, RETRIES):
        try:
            result = [row.entity_id for row in query if entity_filter(row.entity_id)]

            if _LOGGER.isEnabledFor(logging.DEBUG):
                elapsed = time.perf_counter() - timer_start
                _LOGGER.debug(
                    "fetching %d distinct domain/entity_id pairs took %fs",
                    len(result),
                    elapsed,
                )

            return result
        except SQLAlchemyError as err:
            _LOGGER.error("Error executing query: %s", err)

            if tryno == RETRIES - 1:
                raise
            time.sleep(QUERY_RETRY_WAIT)


def _generate_filter_from_config(config):
    excluded_entities = []
    excluded_domains = []
    included_entities = []
    included_domains = []

    exclude = config.get(CONF_EXCLUDE)
    if exclude:
        excluded_entities = exclude.get(CONF_ENTITIES, [])
        excluded_domains = exclude.get(CONF_DOMAINS, [])
    include = config.get(CONF_INCLUDE)
    if include:
        included_entities = include.get(CONF_ENTITIES, [])
        included_domains = include.get(CONF_DOMAINS, [])

    return generate_filter(
        included_domains, included_entities, excluded_domains, excluded_entities
    )


def _get_events(hass, config, start_day, end_day, entity_id=None):
    """Get events for a period of time."""
    entities_filter = _generate_filter_from_config(config)

    def yield_events(query):
        """Yield Events that are not filtered away."""
        for row in query.yield_per(500):
            event = row.to_native()
            if _keep_event(hass, event, entities_filter):
                yield event

    with session_scope(hass=hass) as session:
        if entity_id is not None:
            entity_ids = [entity_id.lower()]
        else:
            entity_ids = _get_related_entity_ids(session, entities_filter)

        query = (
            session.query(Events)
            .order_by(Events.time_fired)
            .outerjoin(States, (Events.event_id == States.event_id))
            .filter(
                Events.event_type.in_(ALL_EVENT_TYPES + list(hass.data.get(DOMAIN, {})))
            )
            .filter((Events.time_fired > start_day) & (Events.time_fired < end_day))
            .filter(
                (
                    (States.last_updated == States.last_changed)
                    & States.entity_id.in_(entity_ids)
                )
                | (States.state_id.is_(None))
            )
        )

        return list(humanify(hass, yield_events(query)))


def _keep_event(hass, event, entities_filter):
    domain, entity_id = None, None

    if event.event_type == EVENT_STATE_CHANGED:
        entity_id = event.data.get("entity_id")

        if entity_id is None:
            return False

        # Do not report on new entities
        old_state = event.data.get("old_state")
        if old_state is None:
            return False

        # Do not report on entity removal
        new_state = event.data.get("new_state")
        if new_state is None:
            return False

        # Do not report on only attribute changes
        if new_state.get("state") == old_state.get("state"):
            return False

        domain = split_entity_id(entity_id)[0]
        attributes = new_state.get("attributes", {})

        # Also filter auto groups.
        if domain == "group" and attributes.get("auto", False):
            return False

        # exclude entities which are customized hidden
        hidden = attributes.get(ATTR_HIDDEN, False)
        if hidden:
            return False

    elif event.event_type == EVENT_LOGBOOK_ENTRY:
        domain = event.data.get(ATTR_DOMAIN)
        entity_id = event.data.get(ATTR_ENTITY_ID)

    elif event.event_type == EVENT_AUTOMATION_TRIGGERED:
        domain = "automation"
        entity_id = event.data.get(ATTR_ENTITY_ID)

    elif event.event_type == EVENT_SCRIPT_STARTED:
        domain = "script"
        entity_id = event.data.get(ATTR_ENTITY_ID)

    elif event.event_type in hass.data.get(DOMAIN, {}):
        domain = hass.data[DOMAIN][event.event_type][0]

    elif event.event_type == EVENT_HOMEKIT_CHANGED:
        domain = DOMAIN_HOMEKIT

    if not entity_id and domain:
        entity_id = f"{domain}."

    return not entity_id or entities_filter(entity_id)


def _entry_message_from_state(domain, state):
    """Convert a state to a message for the logbook."""
    # We pass domain in so we don't have to split entity_id again
    if domain in ["device_tracker", "person"]:
        if state.state == STATE_NOT_HOME:
            return "is away"
        return f"is at {state.state}"

    if domain == "sun":
        if state.state == sun.STATE_ABOVE_HORIZON:
            return "has risen"
        return "has set"

    device_class = state.attributes.get("device_class")
    if domain == "binary_sensor" and device_class:
        if device_class == "battery":
            if state.state == STATE_ON:
                return "is low"
            if state.state == STATE_OFF:
                return "is normal"

        if device_class == "connectivity":
            if state.state == STATE_ON:
                return "is connected"
            if state.state == STATE_OFF:
                return "is disconnected"

        if device_class in ["door", "garage_door", "opening", "window"]:
            if state.state == STATE_ON:
                return "is opened"
            if state.state == STATE_OFF:
                return "is closed"

        if device_class == "lock":
            if state.state == STATE_ON:
                return "is unlocked"
            if state.state == STATE_OFF:
                return "is locked"

        if device_class == "plug":
            if state.state == STATE_ON:
                return "is plugged in"
            if state.state == STATE_OFF:
                return "is unplugged"

        if device_class == "presence":
            if state.state == STATE_ON:
                return "is at home"
            if state.state == STATE_OFF:
                return "is away"

        if device_class == "safety":
            if state.state == STATE_ON:
                return "is unsafe"
            if state.state == STATE_OFF:
                return "is safe"

        if device_class in [
            "cold",
            "gas",
            "heat",
            "light",
            "moisture",
            "motion",
            "occupancy",
            "power",
            "problem",
            "smoke",
            "sound",
            "vibration",
        ]:
            if state.state == STATE_ON:
                return f"detected {device_class}"
            if state.state == STATE_OFF:
                return f"cleared (no {device_class} detected)"

    if state.state == STATE_ON:
        # Future: combine groups and its entity entries ?
        return "turned on"

    if state.state == STATE_OFF:
        return "turned off"

    return f"changed to {state.state}"
