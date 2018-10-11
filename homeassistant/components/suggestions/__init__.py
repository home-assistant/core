"""Component to make suggestions on next actions."""
from collections import Counter
from datetime import timedelta
import json
import logging
from time import monotonic
from pprint import pprint

from homeassistant.const import (
    EVENT_CALL_SERVICE, ATTR_SERVICE_DATA, ATTR_ENTITY_ID)
from homeassistant.components.recorder.util import session_scope
from homeassistant.util import dt as dt_util

DOMAIN = 'suggestions'

DEPENDENCIES = ('recorder',)

NUM_RESULTS = 5

KEY_MORNING = 'morning'
KEY_AFTERNOON = 'afternoon'
KEY_EVENING = 'evening'
KEY_NIGHT = 'night'

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Initialize the suggestion component."""
    await hass.components.recorder.wait_connection_ready()
    results = await hass.async_add_executor_job(_generate_suggestion, hass)
    pprint(results)
    return True


def _generate_suggestion(hass):
    """Generate suggestions.

    Create a dictionary with entity suggestions for time period
    of the day.
    """
    from homeassistant.components.recorder.models import Events
    start = monotonic()
    results = {
        KEY_MORNING: Counter(),
        KEY_AFTERNOON: Counter(),
        KEY_EVENING: Counter(),
        KEY_NIGHT: Counter(),
    }

    week_ago = dt_util.utcnow() - timedelta(days=7)

    with session_scope(hass=hass) as session:
        query = (
            session.query(Events)
            .order_by(Events.time_fired)
            .filter(Events.time_fired > week_ago)
        )

        # Whenever we see a service call for activating a scene or a script,
        # we don't want to count the services called as result from activating.
        # We track that by keeping a context blacklist.
        context_seen = set()
        for event in query.yield_per(500):
            entity_ids = None

            if event.context_id in context_seen:
                continue

            if event.event_type == EVENT_CALL_SERVICE:
                data = json.loads(event.event_data).get(ATTR_SERVICE_DATA, {})
                entity_ids = data.get(ATTR_ENTITY_ID)
                if entity_ids is not None and not isinstance(entity_ids, list):
                    entity_ids = [entity_ids]

                context_seen.add(event.context_id)

            if entity_ids is not None:
                period = _period_from_datetime(
                    dt_util.as_local(event.time_fired))
                for entity_id in entity_ids:
                    results[period][entity_id] += 1

    _LOGGER.info('Generated suggestions in %.3f seconds', monotonic() - start)

    return {
        period: [entity_id for entity_id, count
                 in period_results.most_common(NUM_RESULTS)]
        for period, period_results in results.items()
    }


def _period_from_datetime(date):
    """Convert time to a period key."""
    if date.hour < 6:
        return KEY_NIGHT
    if date.hour < 12:
        return KEY_MORNING
    if date.hour < 18:
        return KEY_AFTERNOON
    return KEY_EVENING
