"""Support for Repetier-Server sensors."""
from datetime import timedelta
import logging

import pyrepetier
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PORT,
    CONF_SENSORS,
    PERCENTAGE,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval
from homeassistant.util import slugify as util_slugify

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "RepetierServer"
DOMAIN = "repetier"
REPETIER_API = "repetier_api"
SCAN_INTERVAL = timedelta(seconds=10)
UPDATE_SIGNAL = "repetier_update_signal"

TEMP_DATA = {"tempset": "temp_set", "tempread": "state", "output": "output"}


API_PRINTER_METHODS = {
    "bed_temperature": {
        "offline": {"heatedbeds": None, "state": "off"},
        "state": {"heatedbeds": "temp_data"},
        "temp_data": TEMP_DATA,
        "attribute": "heatedbeds",
    },
    "extruder_temperature": {
        "offline": {"extruder": None, "state": "off"},
        "state": {"extruder": "temp_data"},
        "temp_data": TEMP_DATA,
        "attribute": "extruder",
    },
    "chamber_temperature": {
        "offline": {"heatedchambers": None, "state": "off"},
        "state": {"heatedchambers": "temp_data"},
        "temp_data": TEMP_DATA,
        "attribute": "heatedchambers",
    },
    "current_state": {
        "offline": {"state": None},
        "state": {
            "state": "state",
            "activeextruder": "active_extruder",
            "hasxhome": "x_homed",
            "hasyhome": "y_homed",
            "haszhome": "z_homed",
            "firmware": "firmware",
            "firmwareurl": "firmware_url",
        },
    },
    "current_job": {
        "offline": {"job": None, "state": "off"},
        "state": {
            "done": "state",
            "job": "job_name",
            "jobid": "job_id",
            "totallines": "total_lines",
            "linessent": "lines_sent",
            "oflayer": "total_layers",
            "layer": "current_layer",
            "speedmultiply": "feed_rate",
            "flowmultiply": "flow",
            "x": "x",
            "y": "y",
            "z": "z",
        },
    },
    "job_end": {
        "offline": {"job": None, "state": "off", "start": None, "printtime": None},
        "state": {
            "job": "job_name",
            "start": "start",
            "printtime": "print_time",
            "printedtimecomp": "from_start",
        },
    },
    "job_start": {
        "offline": {
            "job": None,
            "state": "off",
            "start": None,
            "printedtimecomp": None,
        },
        "state": {"job": "job_name", "start": "start", "printedtimecomp": "from_start"},
    },
}


def has_all_unique_names(value):
    """Validate that printers have an unique name."""
    names = [util_slugify(printer[CONF_NAME]) for printer in value]
    vol.Schema(vol.Unique())(names)
    return value


SENSOR_TYPES = {
    # Type, Unit, Icon, post
    "bed_temperature": ["temperature", TEMP_CELSIUS, "mdi:thermometer", "_bed_"],
    "extruder_temperature": [
        "temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        "_extruder_",
    ],
    "chamber_temperature": [
        "temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        "_chamber_",
    ],
    "current_state": ["state", None, "mdi:printer-3d", ""],
    "current_job": ["progress", PERCENTAGE, "mdi:file-percent", "_current_job"],
    "job_end": ["progress", None, "mdi:clock-end", "_job_end"],
    "job_start": ["progress", None, "mdi:clock-start", "_job_start"],
}

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_API_KEY): cv.string,
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_PORT, default=3344): cv.port,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
                    }
                )
            ],
            has_all_unique_names,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Repetier Server component."""
    hass.data[REPETIER_API] = {}

    for repetier in config[DOMAIN]:
        _LOGGER.debug("Repetier server config %s", repetier[CONF_HOST])

        url = f"http://{repetier[CONF_HOST]}"
        port = repetier[CONF_PORT]
        api_key = repetier[CONF_API_KEY]

        client = pyrepetier.Repetier(url=url, port=port, apikey=api_key)

        printers = client.getprinters()

        if not printers:
            return False

        sensors = repetier[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
        api = PrinterAPI(hass, client, printers, sensors, repetier[CONF_NAME], config)
        api.update()
        track_time_interval(hass, api.update, SCAN_INTERVAL)

        hass.data[REPETIER_API][repetier[CONF_NAME]] = api

    return True


class PrinterAPI:
    """Handle the printer API."""

    def __init__(self, hass, client, printers, sensors, conf_name, config):
        """Set up instance."""
        self._hass = hass
        self._client = client
        self.printers = printers
        self.sensors = sensors
        self.conf_name = conf_name
        self.config = config
        self._known_entities = set()

    def get_data(self, printer_id, sensor_type, temp_id):
        """Get data from the state cache."""
        printer = self.printers[printer_id]
        methods = API_PRINTER_METHODS[sensor_type]
        for prop, offline in methods["offline"].items():
            state = getattr(printer, prop)
            if state == offline:
                # if state matches offline, sensor is offline
                return None

        data = {}
        for prop, attr in methods["state"].items():
            prop_data = getattr(printer, prop)
            if attr == "temp_data":
                temp_methods = methods["temp_data"]
                for temp_prop, temp_attr in temp_methods.items():
                    data[temp_attr] = getattr(prop_data[temp_id], temp_prop)
            else:
                data[attr] = prop_data
        return data

    def update(self, now=None):
        """Update the state cache from the printer API."""
        for printer in self.printers:
            printer.get_data()
        self._load_entities()
        dispatcher_send(self._hass, UPDATE_SIGNAL)

    def _load_entities(self):
        sensor_info = []
        for pidx, printer in enumerate(self.printers):
            for sensor_type in self.sensors:
                info = {}
                info["sensor_type"] = sensor_type
                info["printer_id"] = pidx
                info["name"] = printer.slug
                info["printer_name"] = self.conf_name

                known = f"{printer.slug}-{sensor_type}"
                if known in self._known_entities:
                    continue

                methods = API_PRINTER_METHODS[sensor_type]
                if "temp_data" in methods["state"].values():
                    prop_data = getattr(printer, methods["attribute"])
                    if prop_data is None:
                        continue
                    for idx, _ in enumerate(prop_data):
                        prop_info = info.copy()
                        prop_info["temp_id"] = idx
                        sensor_info.append(prop_info)
                else:
                    info["temp_id"] = None
                    sensor_info.append(info)
                self._known_entities.add(known)

        if not sensor_info:
            return
        load_platform(self._hass, "sensor", DOMAIN, sensor_info, self.config)
