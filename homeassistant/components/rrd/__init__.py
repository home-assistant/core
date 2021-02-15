"""Support for sending data to an RRD database."""
import logging
import os.path
import time

import rrdtool
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_PATH,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CF,
    CONF_DBS,
    CONF_DS,
    CONF_HEARTBEAT,
    CONF_MAX,
    CONF_MIN,
    CONF_ROWS,
    CONF_RRA,
    CONF_SENSOR,
    CONF_STEP,
    CONF_STEPS,
    CONF_XFF,
    DEFAULT_STEP,
    DOMAIN,
    RRD_DIR,
)
from .utils import convert_to_seconds, rrd_scaled_duration

DS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_CF): vol.In(
            ["GAUGE", "COUNTER", "DERIVE", "DCOUNTER", "DDERIVE", "ABSOLUTE"]
        ),
        vol.Required(CONF_HEARTBEAT): rrd_scaled_duration,
        vol.Optional(CONF_MIN): cv.Number,
        vol.Optional(CONF_MAX): cv.Number,
    },
    extra=vol.ALLOW_EXTRA,
)

RRA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CF): vol.In(["AVERAGE", "MIN", "MAX", "LAST"]),
        vol.Optional(CONF_XFF, default=0.5): vol.Range(min=0, max=1),
        vol.Required(CONF_STEPS): rrd_scaled_duration,
        vol.Required(CONF_ROWS): rrd_scaled_duration,
    },
    extra=vol.ALLOW_EXTRA,
)

DB_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_STEP, default=DEFAULT_STEP): rrd_scaled_duration,
        vol.Required(CONF_DS): vol.All(cv.ensure_list, [DS_SCHEMA]),
        vol.Required(CONF_RRA): vol.All(cv.ensure_list, [RRA_SCHEMA]),
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_PATH, default=RRD_DIR): cv.string,
                vol.Required(CONF_DBS): vol.All(cv.ensure_list, [DB_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Set up the RRD Recorder component."""
    _LOGGER.debug("Setup started")
    conf = config[DOMAIN]
    entities = {}  # Mapping and caching of entities <-> data sources

    # Create RRD files, if not exist yet.
    for database in conf[CONF_DBS]:
        datasources = []
        rras = []
        for ds in database[CONF_DS]:
            ds_string = f"DS:{ds[CONF_NAME]}:{ds[CONF_CF]}:{ds[CONF_HEARTBEAT]}:{ds.get(CONF_MIN, 'U')}:{ds.get(CONF_MAX, 'U')}"
            datasources.append(ds_string)
            entities[ds[CONF_SENSOR]] = ds[CONF_NAME], 0, None

        for rra in database[CONF_RRA]:
            # CONF_CF:
            # - AVERAGE: Average value for the step period.
            # - MIN: Min value for the step period.
            # - MAX: Max value for the step period.
            # - LAST: Last value for the step period which got inserted by the update script.
            # CONF_XFF: What percentage of UNKNOWN data is allowed so that the consolidated value
            #           is still regarded as known: 0% - 99%. Typical is 50%. Value in range 0-1
            # CONF_STEPS: How many step values will be used to build a single archive entry.
            rras.append(
                f"RRA:{rra[CONF_CF]}:{rra[CONF_XFF]}:{rra[CONF_STEPS]}:{rra[CONF_ROWS]}"
            )

        rrd_dir = conf[CONF_PATH]
        rrd_filename = hass.config.path(rrd_dir, database[CONF_NAME]) + ".rrd"

        try:
            if not os.path.exists(hass.config.path(rrd_dir)):
                _LOGGER.debug("Creating %s", hass.config.path(rrd_dir))
                os.makedirs(hass.config.path(rrd_dir))
            if not os.path.isfile(rrd_filename):
                # TODO: Make this a service to overwrite the file afterward only on request
                _LOGGER.debug("Creating file %s", rrd_filename)

                rrdtool.create(
                    rrd_filename,
                    "--start",
                    "now",
                    "--step",
                    database[CONF_STEP],
                    *rras,
                    *datasources,
                )
        except rrdtool.OperationalError as exc:
            _LOGGER.error(exc)
            return False

    # List of scheduled updates. Used for cancellation during the HASS shutting down.
    cancel_callbacks = {}

    def schedule_next_update(database):
        # Scheduling
        step = convert_to_seconds(database[CONF_STEP])

        now = time.time()
        next_update_timestamp = ((now // step) + 1) * step
        update_after = next_update_timestamp - now
        cancel_callback = hass.loop.call_at(
            hass.loop.time() + update_after, update, database
        )

        # Add cancel callback for cancellation during HASS shutting down.
        database_name = database[CONF_NAME]
        cancel_callbacks[database_name] = cancel_callback

    def update(database):
        rrd_filename = hass.config.path(rrd_dir, database[CONF_NAME]) + ".rrd"

        # RRD data source names for store.
        ds_names = []
        # RRD data source values for store. Corresponding with `ds_names` variable.
        ds_values = []

        # Prepare parameters with all sensor values for `rrdtool` command
        for data_source in database[CONF_DS]:
            sensor_id = data_source[CONF_SENSOR]
            ds_name = data_source[CONF_NAME]

            # Get data value
            sensor_state = hass.states.get(sensor_id)
            try:
                if sensor_state is None:
                    _LOGGER.debug(
                        "[%s] Skipping sensor %s, because value is unknown.",
                        rrd_filename,
                        sensor_id,
                    )
                    raise Exception("Sensor has no value or not exists.")

                sensor_value = sensor_state.state
                # Convert value to integer, when type is COUNTER or DERIVE.
                if data_source[CONF_CF] in ["COUNTER", "DERIVE"]:
                    sensor_value = round(float(sensor_value))
            except Exception:
                _LOGGER.info(
                    "[%s] sensor %s value will be stored as NaN.",
                    rrd_filename,
                    sensor_id,
                )
                sensor_value = "NaN"

            # Add pairs of name, value. Will be used as parameters for data save to rrd file.
            ds_names.append(ds_name)
            ds_values.append(str(sensor_value))

        # Save to RRD file
        try:
            template = ":".join(ds_names)
            timestamp = int(time.time())
            values_string = ":".join(ds_values)

            rrdtool.update(
                rrd_filename, f"-t{template}", f"{timestamp}:{values_string}"
            )
            _LOGGER.debug(
                "%s data added. ds=%s, values=%s:%s",
                rrd_filename,
                template,
                timestamp,
                values_string,
            )
        except rrdtool.OperationalError as exc:
            _LOGGER.error(exc)

        # Schedule next update
        schedule_next_update(database)

    # Executed on Home assistant start
    def start(_):
        try:
            for database in conf[CONF_DBS]:
                # Run each database updating in own thread.
                schedule_next_update(database)

        except Exception as exc:
            _LOGGER.error(exc)

    # Stop updating all RRD files, because HASS is shutting down
    def stop(_):
        _LOGGER.debug("Stopping data updating")

        # Cancel all already scheduled updates
        for cancel_callback in cancel_callbacks.values():
            cancel_callback.cancel()

    # Start to store data after app start
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start)

    # Stop updating in all threads in case of Home Assistant shutting down
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    _LOGGER.debug("Setup finished")

    return True
