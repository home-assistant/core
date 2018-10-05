"""
Exports events as CSV file.

Component that records all events as lines in a CSV file.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/csv/
"""
import concurrent.futures
import logging
import queue
import threading
import os
from typing import Dict

import asyncio
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN)
from homeassistant.core import CoreState, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.helpers.typing import ConfigType

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'csv'

CONF_DATA_DIR = 'data_dir'
CONF_SEPARATOR = 'separator'

FILTER_SCHEMA = vol.Schema({
    vol.Optional(CONF_EXCLUDE, default={}): vol.Schema({
        vol.Optional(CONF_DOMAINS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_ENTITIES): cv.entity_ids,
    }),
    vol.Optional(CONF_INCLUDE, default={}): vol.Schema({
        vol.Optional(CONF_DOMAINS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_ENTITIES): cv.entity_ids,
    })
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: FILTER_SCHEMA.extend({
        vol.Required(CONF_DATA_DIR): cv.string,
        vol.Optional(CONF_SEPARATOR, default=','): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the recorder."""
    conf = config.get(DOMAIN, {})
    data_dir = conf.get(CONF_DATA_DIR)
    separator = conf.get(CONF_SEPARATOR)
    include = conf.get(CONF_INCLUDE, {})
    exclude = conf.get(CONF_EXCLUDE, {})

    if not os.path.isdir(data_dir):
        _LOGGER.error("Value of '%s' does not point to an existing directory: "
                      "%s", CONF_DATA_DIR, data_dir)
        return False

    instance = hass.data[DOMAIN] = Csv(hass=hass, data_dir=data_dir,
                                       include=include, exclude=exclude,
                                       separator=separator)
    instance.async_initialize()
    instance.start()

    return True


class Csv(threading.Thread):
    """Thread that writes to the file."""

    def __init__(self, hass: HomeAssistant, data_dir: str,
                 include: Dict, exclude: Dict, separator: str) -> None:
        """Initialize the recorder."""
        threading.Thread.__init__(self, name='CSV')
        self.hass = hass
        self.data_dir = data_dir
        self.separator = separator
        self.queue = queue.Queue()
        self.async_db_ready = asyncio.Future(loop=hass.loop)

        self.entity_filter = generate_filter(
            include.get(CONF_DOMAINS, []), include.get(CONF_ENTITIES, []),
            exclude.get(CONF_DOMAINS, []), exclude.get(CONF_ENTITIES, []))

    @callback
    def async_initialize(self):
        """Initialize the thread."""
        self.hass.bus.async_listen(EVENT_STATE_CHANGED, self.event_listener)

    @callback
    def event_listener(self, event):
        """Listen for new events."""
        if _LOGGER.isEnabledFor(logging.DEBUG) and event is not None:
            _LOGGER.debug("Got new event: %s",
                          event.data.get(ATTR_ENTITY_ID))
        self.queue.put(event)

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()

    def run(self):
        """Start processing events."""
        shutdown_task = object()
        hass_started = concurrent.futures.Future()

        @callback
        def register():
            """Post connection initialize."""
            def shutdown(event):
                """Shut down the Recorder."""
                if not hass_started.done():
                    hass_started.set_result(shutdown_task)
                self.queue.put(None)
                self.join()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

            if self.hass.state == CoreState.running:
                hass_started.set_result(None)
            else:
                @callback
                def notify_hass_started(event):
                    """Notify that hass has started."""
                    hass_started.set_result(None)

                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_START, notify_hass_started)

        self.hass.add_job(register)
        result = hass_started.result()

        # If shutdown happened before Home Assistant finished starting
        if result is shutdown_task:
            return

        while True:
            event = self.queue.get()

            if event is None:
                self.queue.task_done()
                return

            entity_id = event.data.get(ATTR_ENTITY_ID)
            if entity_id is not None:
                if not self.entity_filter(entity_id):
                    if _LOGGER.isEnabledFor(logging.DEBUG):
                        _LOGGER.debug(
                            "Ignoring event because it is excluded: %s",
                            entity_id)
                    self.queue.task_done()
                    continue

            new_state = event.data.get('new_state')
            if new_state is None or new_state.state in (
                    STATE_UNKNOWN, '', STATE_UNAVAILABLE):
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("Ignoring event because state is n.a.: %s",
                                  entity_id)
                self.queue.task_done()
                continue

            origin = event.origin
            time_fired = event.time_fired
            file_name = 'events_' + time_fired.strftime("%Y-%m-%d") + '.csv'
            file_path = os.path.join(self.data_dir, file_name)

            try:
                with open(file_path, 'a') as csv_file:
                    line = "{}{}{}{}{}{}{}\n".format(entity_id,
                                                     self.separator,
                                                     time_fired.isoformat(),
                                                     self.separator,
                                                     origin,
                                                     self.separator,
                                                     new_state.state)
                    csv_file.write(line)
                    csv_file.flush()
                    if _LOGGER.isEnabledFor(logging.DEBUG):
                        _LOGGER.debug("Written line: %s", line.rstrip())
            except IOError as err:
                _LOGGER.error("Failed to write to file %s: %s",
                              file_path, err)

            self.queue.task_done()
