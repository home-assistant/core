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
import gzip
import shutil
from datetime import datetime

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
CONF_GZIP = 'gzip'
CONF_PURGE_KEEP_DAYS = 'purge_keep_days'

CONST_PREFIX_FILE = 'events_'
CONST_DATE_FORMAT = "%Y-%m-%d"
CONST_DATE_FORMAT_LEN = 10

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
        vol.Required(CONF_DATA_DIR): vol.All(cv.isdir, cv.string),
        vol.Optional(CONF_SEPARATOR, default=','): cv.string,
        vol.Optional(CONF_GZIP, default=True): cv.boolean,
        vol.Optional(CONF_PURGE_KEEP_DAYS, default=10):
            vol.All(vol.Coerce(int), vol.Range(min=1))
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the recorder."""
    conf = config.get(DOMAIN, {})
    data_dir = conf.get(CONF_DATA_DIR)
    separator = conf.get(CONF_SEPARATOR)
    gzip_conf = conf.get(CONF_GZIP)
    purge_keep_days = conf.get(CONF_PURGE_KEEP_DAYS)
    include = conf.get(CONF_INCLUDE, {})
    exclude = conf.get(CONF_EXCLUDE, {})

    if not os.path.isdir(data_dir):
        _LOGGER.error("Value of '%s' does not point to an existing directory: "
                      "%s", CONF_DATA_DIR, data_dir)
        return False

    instance = hass.data[DOMAIN] = Csv(hass=hass, data_dir=data_dir,
                                       include=include, exclude=exclude,
                                       separator=separator,
                                       gzip_conf=gzip_conf,
                                       purge_keep_days=purge_keep_days)
    instance.async_initialize()
    instance.start()

    return True


class Csv(threading.Thread):
    """Thread that writes to the file."""

    def __init__(self, hass: HomeAssistant, data_dir: str,
                 include: Dict, exclude: Dict, separator: str,
                 gzip_conf: bool, purge_keep_days: int) -> None:
        """Initialize the recorder."""
        threading.Thread.__init__(self, name='CSV')
        self.hass = hass
        self.data_dir = data_dir
        self.separator = separator
        self.gzip_conf = gzip_conf
        self.last_run_day = None
        self.purge_keep_days = purge_keep_days
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
            time_fired_date = time_fired.strftime(CONST_DATE_FORMAT)
            file_name = CONST_PREFIX_FILE + time_fired_date + '.csv'
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

            if self.gzip_conf or self.purge_keep_days > 0:
                if self.last_run_day is None or \
                   self.last_run_day != time_fired_date:
                    try:
                        self._process_old_files(file_name, time_fired)
                    finally:
                        self.last_run_day = time_fired_date

            self.queue.task_done()

    def _process_old_files(self, curr_file_name, time_fired):
        """Gzip/Remove files from previous days."""
        # pylint: disable=W0612
        for dirpath, dirnames, filenames in os.walk(self.data_dir):
            for filename in filenames:
                if filename.startswith(CONST_PREFIX_FILE) \
                   and not filename == curr_file_name:
                    file_path = os.path.join(dirpath, filename)
                    if self._file_too_old(filename, time_fired):
                        try:
                            os.remove(file_path)
                        except IOError as err:
                            _LOGGER.error("Failed to remove file %s: %s",
                                          file_path, err)
                    elif filename.endswith('.csv'):
                        try:
                            with open(file_path, 'rb') as fin, \
                                    gzip.open(file_path + '.gz', 'wb') as fout:
                                shutil.copyfileobj(fin, fout)
                            os.remove(file_path)
                        except IOError as err:
                            _LOGGER.error("Failed to gzip file %s: %s",
                                          file_path, err)

    def _file_too_old(self, filename, time_fired) -> bool:
        """Check if file is too old."""
        too_old = False
        if len(filename) > (len(CONST_PREFIX_FILE) + CONST_DATE_FORMAT_LEN):
            end_of_date = len(CONST_PREFIX_FILE) + CONST_DATE_FORMAT_LEN
            date_part = filename[len(CONST_PREFIX_FILE):end_of_date]
            parsed = datetime.strptime(date_part, CONST_DATE_FORMAT)
            tfired = time_fired.replace(tzinfo=None)
            delta = tfired - parsed
            if delta.days > self.purge_keep_days:
                too_old = True
        return too_old
