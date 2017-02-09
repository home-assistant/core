"""
Support for restoring entity states on startup.

Component that records all events and state changes. Allows other components
to query this database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/recorder/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, ATTR_RESTORED_STATE)
from homeassistant.components.history import (
    CONF_DOMAINS, CONF_EXCLUDE, CONF_ENTITIES, CONF_INCLUDE,
    Filters, get_states, last_recorder_run, recorder)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

DOMAIN = 'restore_state'

DEPENDENCES = ['recorder']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: cv.FILTER_SCHEMA,
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Restore states."""
    filters = Filters()
    exclude = config[DOMAIN].get(CONF_EXCLUDE)
    if exclude:
        filters.excluded_entities = exclude[CONF_ENTITIES]
        filters.excluded_domains = exclude[CONF_DOMAINS]
    include = config[DOMAIN].get(CONF_INCLUDE)
    if include:
        filters.included_entities = include[CONF_ENTITIES]
        filters.included_domains = include[CONF_DOMAINS]

    # Wait for the recorder
    recorder.get_instance()

    last_run = last_recorder_run()
    if last_run is None:
        return

    last_end_time = last_run.end - timedelta(seconds=1)
    # Unfortunately the recorder_run model do not return offset-aware time
    last_end_time = last_end_time.replace(tzinfo=dt_util.UTC)
    _LOGGER.debug("Last run: %s - %s", last_run.start, last_end_time)

    states = get_states(last_end_time, run=last_run, filters=filters)

    # Cache the states
    hass.data[ATTR_RESTORED_STATE] = {
        state.entity_id: state for state in states}

    def remove_cache(event):
        """Remove the states cache."""
        del hass.data[ATTR_RESTORED_STATE]

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, remove_cache)

    return True
