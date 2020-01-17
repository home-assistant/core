"""Config flow for konnected.io integration."""
import asyncio
from collections import OrderedDict
import copy
import logging
from urllib.parse import urlparse

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASSES as BIN_SENS_TYPES,
    DEVICE_CLASSES_SCHEMA,
)
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PIN,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_TYPE,
    CONF_ZONE,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ACTIVATION,
    CONF_BLINK,
    CONF_DISCOVERY,
    CONF_INVERSE,
    CONF_MOMENTARY,
    CONF_PAUSE,
    CONF_POLL_INTERVAL,
    CONF_REPEAT,
    DOMAIN,
    PIN_TO_ZONE,
    STATE_HIGH,
    STATE_LOW,
    ZONES,
)
from .errors import CannotConnect
from .panel import KONN_MODEL, KONN_MODEL_PRO, get_status

_LOGGER = logging.getLogger(__name__)

ATTR_KONN_UPNP_MODEL_NAME = "model_name"  # standard upnp is modelName

KONN_MANUFACTURER = "konnected.io"
KONN_PANEL_MODEL_NAMES = {
    KONN_MODEL: "Konnected Alarm Panel",
    KONN_MODEL_PRO: "Konnected Alarm Panel Pro",
}

DATA_SCHEMA_MANUAL = OrderedDict()
DATA_SCHEMA_MANUAL[vol.Required(CONF_HOST)] = str
DATA_SCHEMA_MANUAL[vol.Required(CONF_PORT)] = int

OPTIONS_IO_ANY = vol.In(
    ["Disabled", "Binary Sensor", "Digital Sensor", "Switchable Output"]
)
OPTIONS_IO_INPUT_ONLY = vol.In(["Disabled", "Binary Sensor", "Digital Sensor"])
OPTIONS_IO_OUTPUT_ONLY = vol.In(["Disabled", "Switchable Output"])

DATA_SCHEMA_KONN_MODEL = OrderedDict()
DATA_SCHEMA_KONN_MODEL[vol.Required("1", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL[vol.Required("2", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL[vol.Required("3", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL[vol.Required("4", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL[vol.Required("5", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL[vol.Required("6", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL[vol.Required("out", default="Disabled")] = OPTIONS_IO_OUTPUT_ONLY


DATA_SCHEMA_KONN_MODEL_PRO_1 = OrderedDict()
DATA_SCHEMA_KONN_MODEL_PRO_1[vol.Required("1", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL_PRO_1[vol.Required("2", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL_PRO_1[vol.Required("3", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL_PRO_1[vol.Required("4", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL_PRO_1[vol.Required("5", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL_PRO_1[vol.Required("6", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL_PRO_1[vol.Required("7", default="Disabled")] = OPTIONS_IO_ANY

DATA_SCHEMA_KONN_MODEL_PRO_2 = OrderedDict()
DATA_SCHEMA_KONN_MODEL_PRO_2[vol.Required("8", default="Disabled")] = OPTIONS_IO_ANY
DATA_SCHEMA_KONN_MODEL_PRO_2[
    vol.Required("9", default="Disabled")
] = OPTIONS_IO_INPUT_ONLY
DATA_SCHEMA_KONN_MODEL_PRO_2[
    vol.Required("11", default="Disabled")
] = OPTIONS_IO_INPUT_ONLY
DATA_SCHEMA_KONN_MODEL_PRO_2[
    vol.Required("12", default="Disabled")
] = OPTIONS_IO_INPUT_ONLY
DATA_SCHEMA_KONN_MODEL_PRO_2[
    vol.Required("alarm1", default="Disabled")
] = OPTIONS_IO_OUTPUT_ONLY
DATA_SCHEMA_KONN_MODEL_PRO_2[
    vol.Required("out1", default="Disabled")
] = OPTIONS_IO_OUTPUT_ONLY
DATA_SCHEMA_KONN_MODEL_PRO_2[
    vol.Required("alarm2_out2", default="Disabled")
] = OPTIONS_IO_OUTPUT_ONLY


DATA_SCHEMA_BIN_SENSOR_OPTIONS = OrderedDict()
DATA_SCHEMA_BIN_SENSOR_OPTIONS[
    vol.Required("type", default=DEVICE_CLASS_DOOR)
] = vol.In(BIN_SENS_TYPES)
DATA_SCHEMA_BIN_SENSOR_OPTIONS[vol.Optional("name")] = str
DATA_SCHEMA_BIN_SENSOR_OPTIONS[vol.Optional("inverse", default=False)] = bool

DATA_SCHEMA_SENSOR_OPTIONS = OrderedDict()
DATA_SCHEMA_SENSOR_OPTIONS[vol.Required("type")] = vol.In(["dht", "ds18b20"])
DATA_SCHEMA_SENSOR_OPTIONS[vol.Optional("name")] = str
DATA_SCHEMA_SENSOR_OPTIONS[vol.Optional("poll_interval")] = vol.All(
    int, vol.Range(min=1)
)

DATA_SCHEMA_SWITCH_OPTIONS = OrderedDict()
DATA_SCHEMA_SWITCH_OPTIONS[vol.Optional("name")] = str
DATA_SCHEMA_SWITCH_OPTIONS[vol.Optional("activation", default="high")] = vol.In(
    ["low", "high"]
)
DATA_SCHEMA_SWITCH_OPTIONS[vol.Optional("momentary")] = int
DATA_SCHEMA_SWITCH_OPTIONS[vol.Optional("pause")] = int
DATA_SCHEMA_SWITCH_OPTIONS[vol.Optional("repeat")] = int

DATA_SCHEMA_OPTIONS = {
    "Binary Sensor": DATA_SCHEMA_BIN_SENSOR_OPTIONS,
    "Sensor": DATA_SCHEMA_SENSOR_OPTIONS,
    "Switch": DATA_SCHEMA_SWITCH_OPTIONS,
}


def ensure_pin(value):
    """Check if valid pin and coerce to string."""
    if value is None:
        raise vol.Invalid("pin value is None")

    if PIN_TO_ZONE.get(str(value)) is None:
        raise vol.Invalid("pin not valid")

    return str(value)


def ensure_zone(value):
    """Check if valid zone and coerce to string."""
    if value is None:
        raise vol.Invalid("zone value is None")

    if str(value) not in ZONES is None:
        raise vol.Invalid("zone not valid")

    return str(value)


# configuration.yaml schemas (legacy)
BINARY_SENSOR_SCHEMA_YAML = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_ZONE, "s_zone"): ensure_zone,
            vol.Exclusive(CONF_PIN, "s_pin"): ensure_pin,
            vol.Required(CONF_TYPE): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_INVERSE, default=False): cv.boolean,
        }
    ),
    cv.has_at_least_one_key(CONF_PIN, CONF_ZONE),
)

SENSOR_SCHEMA_YAML = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_ZONE, "s_zone"): ensure_zone,
            vol.Exclusive(CONF_PIN, "s_pin"): ensure_pin,
            vol.Required(CONF_TYPE): vol.All(vol.Lower, vol.In(["dht", "ds18b20"])),
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_POLL_INTERVAL, default=3): vol.All(
                vol.Coerce(int), vol.Range(min=1)
            ),
        }
    ),
    cv.has_at_least_one_key(CONF_PIN, CONF_ZONE),
)

SWITCH_SCHEMA_YAML = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_ZONE, "s_zone"): ensure_zone,
            vol.Exclusive(CONF_PIN, "s_pin"): ensure_pin,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_ACTIVATION, default=STATE_HIGH): vol.All(
                vol.Lower, vol.Any(STATE_HIGH, STATE_LOW)
            ),
            vol.Optional(CONF_MOMENTARY): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Optional(CONF_PAUSE): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Optional(CONF_REPEAT): vol.All(vol.Coerce(int), vol.Range(min=-1)),
        }
    ),
    cv.has_at_least_one_key(CONF_PIN, CONF_ZONE),
)

DEVICE_SCHEMA_YAML = vol.Schema(
    {
        vol.Required(CONF_ID): cv.matches_regex("[0-9a-f]{12}"),
        vol.Optional(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list, [BINARY_SENSOR_SCHEMA_YAML]
        ),
        vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [SENSOR_SCHEMA_YAML]),
        vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [SWITCH_SCHEMA_YAML]),
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_BLINK, default=True): cv.boolean,
        vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
    }
)

# Config entry schemas
BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE, "s_zone"): vol.In(ZONES),
        vol.Required(CONF_TYPE): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_INVERSE, default=False): cv.boolean,
    }
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE, "s_zone"): vol.In(ZONES),
        vol.Required(CONF_TYPE): vol.All(vol.Lower, vol.In(["dht", "ds18b20"])),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_POLL_INTERVAL, default=3): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
    }
)

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE, "s_zone"): vol.In(ZONES),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ACTIVATION, default=STATE_HIGH): vol.All(
            vol.Lower, vol.Any(STATE_HIGH, STATE_LOW)
        ),
        vol.Optional(CONF_MOMENTARY): vol.All(vol.Coerce(int), vol.Range(min=10)),
        vol.Optional(CONF_PAUSE): vol.All(vol.Coerce(int), vol.Range(min=10)),
        vol.Optional(CONF_REPEAT): vol.All(vol.Coerce(int), vol.Range(min=-1)),
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.matches_regex("[0-9a-f]{12}"),
        vol.Optional(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list, [BINARY_SENSOR_SCHEMA]
        ),
        vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [SENSOR_SCHEMA]),
        vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [SWITCH_SCHEMA]),
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_BLINK, default=True): cv.boolean,
        vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
    }
)


@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(
        entry.data.get("host") for entry in hass.config_entries.async_entries(DOMAIN)
    )


@callback
def configured_devices(hass):
    """Return a set of the configured devices."""
    return set(entry.data["id"] for entry in hass.config_entries.async_entries(DOMAIN))


class KonnectedFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NEW_NAME."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167

    def __init__(self):
        """Initialize the Konnected flow."""
        self.host = None
        self.port = None
        self.model = KONN_MODEL
        self.device_id = None

        # data above builds the config entry
        # data below maintains state between steps
        self.io_cfg = {}
        self.binary_sensors = []
        self.sensors = []
        self.switches = []
        self.active_cfg = None

    @property
    def cached_config(self):
        """Retrieve cached config for device."""
        if self.hass.data.get(DOMAIN) and self.hass.data[DOMAIN].get("config_data"):
            return self.hass.data[DOMAIN]["config_data"].get(self.device_id)
        return None

    @callback
    def async_cache_config(self, config):
        """Cache the device config for shared usage."""
        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
            self.hass.data[DOMAIN]["config_data"] = {}

        self.hass.data[DOMAIN]["config_data"][self.device_id] = config

    async def async_step_init(self, user_input=None):
        """Needed in order to not require re-translation of strings."""
        return await self.async_step_user(user_input)

    async def async_step_import(self, import_info):
        """Import a configuration.yaml config.

        This flow is triggered by `async_setup` for configured panels.
        Triggered for any panel that does not have a config entry
        yet (based on device_id).  If the cfg entry can't be made
        we'll cache the data in hass.data[DOMAIN]["config_data"] for
        other flows to reference.
        """
        _LOGGER.debug(import_info)
        try:
            device_config = DEVICE_SCHEMA_YAML(import_info)

        except vol.Invalid as err:
            _LOGGER.error(
                "Cannot import config..%s", humanize_error(import_info, err),
            )
            return self.async_abort(reason="unknown")

        # swap out pin for zones in a io config
        def pins_to_zones(config):
            for zone in config:
                if zone.get(CONF_PIN):
                    zone[CONF_ZONE] = PIN_TO_ZONE[zone[CONF_PIN]]
                    del zone[CONF_PIN]

        if device_config.get(CONF_BINARY_SENSORS):
            pins_to_zones(device_config[CONF_BINARY_SENSORS])

        if device_config.get(CONF_SENSORS):
            pins_to_zones(device_config[CONF_SENSORS])

        if device_config.get(CONF_SWITCHES):
            pins_to_zones(device_config[CONF_SWITCHES])

        self.device_id = self.context["device_id"] = device_config["id"]
        try:
            self.host = device_config[CONF_HOST]
            self.port = device_config[CONF_PORT]

        except KeyError:
            # cache config and wait for user input or discovery to provide host info
            self.async_cache_config(device_config)
            return await self.async_step_user()

        # create the config entry
        return await self.async_create_or_update_entry(device_config)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input:
            try:
                self.host = user_input[CONF_HOST]
                self.port = user_input[CONF_PORT]

                # try to obtain the mac address from the device
                status = await get_status(self.hass, self.host, self.port)
                self.device_id = status.get("mac").replace(":", "")
                self.model = status.get("name", KONN_MODEL)

                # finish if we have a cached data set (partial config imported earlier)
                if self.cached_config:
                    config = copy.deepcopy(self.cached_config)
                    try:
                        config[CONF_HOST] = self.host
                        config[CONF_PORT] = self.port
                        return await self.async_create_or_update_entry(
                            DEVICE_SCHEMA(config)
                        )

                    except vol.Invalid as err:
                        _LOGGER.warning(
                            "Invalid cached config..%s", humanize_error(config, err),
                        )

                return await self.async_step_io()

            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA_MANUAL), errors=errors
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered konnected panel.

        This flow is triggered by the SSDP component. It will check if the
        device is already configured and attempt to finish the config if not.
        """
        from homeassistant.components.ssdp import (
            ATTR_UPNP_MANUFACTURER,
            ATTR_UPNP_MODEL_NAME,
        )

        _LOGGER.debug(discovery_info)

        try:
            if discovery_info[ATTR_UPNP_MANUFACTURER] != KONN_MANUFACTURER:
                return self.async_abort(reason="not_konn_panel")

            if not any(
                name in discovery_info[ATTR_UPNP_MODEL_NAME]
                for name in KONN_PANEL_MODEL_NAMES
            ):
                _LOGGER.warning(
                    "Discovered unrecognized Konnected device %s",
                    discovery_info.get(ATTR_UPNP_MODEL_NAME, "Unknown"),
                )
                return self.async_abort(reason="not_konn_panel")

            # extract host/port from ssdp_location
            netloc = urlparse(discovery_info["ssdp_location"]).netloc.split(":")
            self.host = self.context["host"] = netloc[0]
            self.port = netloc[1]
            self.model = discovery_info[ATTR_UPNP_MODEL_NAME]

        except KeyError:
            _LOGGER.error("Malformed Konnected SSDP info")
            return self.async_abort(reason="unknown")

        if any(
            self.host == flow["context"].get("host")
            for flow in self._async_in_progress()
        ):
            return self.async_abort(reason="already_in_progress")

        if self.host in configured_hosts(self.hass):
            return self.async_abort(reason="already_configured")

        # brief delay to allow processing of recent status req
        await asyncio.sleep(0.1)

        # try to obtain the mac address from the device
        try:
            self.device_id = self.context["device_id"] = (
                (await get_status(self.hass, self.host, self.port))
                .get("mac")
                .replace(":", "")
            )

        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        if not self.device_id:
            return self.async_abort(reason="cannot_connect")

        # look for a partially configured instance of this device and hijack it
        for flow in self.hass.config_entries.flow.async_progress():
            if flow["handler"] == self.handler and flow["flow_id"] != self.flow_id:
                if (
                    self.device_id == flow["context"].get("device_id")
                    and self.cached_config
                ):
                    # steal the config data and abort other flow
                    # only would happen if the other flow was imported config.yaml w/o host info
                    _LOGGER.info("Konnected partially imported - completing cfg entry")
                    config = copy.deepcopy(self.cached_config)
                    config[CONF_HOST] = self.host
                    config[CONF_PORT] = self.port
                    self.hass.config_entries.flow.async_abort(flow["flow_id"])
                    return await self.async_create_or_update_entry(config)

        # if this device exists but the host is different we will utilize it's cfg
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if self.device_id == entry.data["id"]:
                _LOGGER.info("Konnected host changed - creating replacement cfg entry")
                config = copy.deepcopy(entry.data)
                config[CONF_HOST] = self.host
                config[CONF_PORT] = self.port
                return await self.async_create_or_update_entry(config)

        return await self.async_step_io()

    async def async_step_io(self, user_input=None):
        """Allow the user to configure the IO."""
        errors = {}
        if user_input is not None:
            # strip out disabled io and save for options cfg
            self.io_cfg = {}
            for key, value in user_input.items():
                if value != "Disabled":
                    self.io_cfg.update({key: value})
            return await self.async_step_io_ext()

        if self.model == KONN_MODEL:
            return self.async_show_form(
                step_id="io",
                data_schema=vol.Schema(DATA_SCHEMA_KONN_MODEL),
                description_placeholders={
                    "model": KONN_PANEL_MODEL_NAMES[self.model],
                    "host": self.host,
                },
                errors=errors,
            )

        # configure the first half of the pro board io
        if self.model == KONN_MODEL_PRO:
            return self.async_show_form(
                step_id="io",
                data_schema=vol.Schema(DATA_SCHEMA_KONN_MODEL_PRO_1),
                description_placeholders={
                    "model": KONN_PANEL_MODEL_NAMES[self.model],
                    "host": self.host,
                },
                errors=errors,
            )

        return self.async_abort(reason="not_konn_panel")

    async def async_step_io_ext(self, user_input=None):
        """Allow the user to configure the extended IO for pro."""
        errors = {}
        if user_input is not None:
            # strip out disabled io and save for options cfg
            for key, value in user_input.items():
                if value != "Disabled":
                    self.io_cfg.update({key: value})
            return await self.async_step_options_binary()

        if self.model == KONN_MODEL:
            return await self.async_step_options_binary()

        if self.model == KONN_MODEL_PRO:
            return self.async_show_form(
                step_id="io_ext",
                data_schema=vol.Schema(DATA_SCHEMA_KONN_MODEL_PRO_2),
                description_placeholders={
                    "model": KONN_PANEL_MODEL_NAMES[self.model],
                    "host": self.host,
                },
                errors=errors,
            )

        return self.async_abort(reason="not_konn_panel")

    async def async_step_options_binary(self, user_input=None):
        """Allow the user to configure the IO options for binary sensors."""
        errors = {}
        if user_input is not None:
            zone = {"zone": self.active_cfg}
            zone.update(user_input)
            self.binary_sensors.append(zone)
            self.io_cfg.pop(self.active_cfg)
            self.active_cfg = None

        if self.active_cfg:
            return self.async_show_form(
                step_id="options_binary",
                data_schema=vol.Schema(DATA_SCHEMA_BIN_SENSOR_OPTIONS),
                description_placeholders={
                    "zone": "Zone " + self.active_cfg
                    if len(self.active_cfg) < 3
                    else self.active_cfg.upper
                },
                errors=errors,
            )

        # find the next unconfigured binary sensor
        for key, value in self.io_cfg.items():
            if value == "Binary Sensor":
                self.active_cfg = key
                return self.async_show_form(
                    step_id="options_binary",
                    data_schema=vol.Schema(DATA_SCHEMA_BIN_SENSOR_OPTIONS),
                    description_placeholders={
                        "zone": "Zone " + self.active_cfg
                        if len(self.active_cfg) < 3
                        else self.active_cfg.upper
                    },
                    errors=errors,
                )

        return await self.async_step_options_digital()

    async def async_step_options_digital(self, user_input=None):
        """Allow the user to configure the IO options for digital sensors."""
        errors = {}
        if user_input is not None:
            zone = {"zone": self.active_cfg}
            zone.update(user_input)
            self.sensors.append(zone)
            self.io_cfg.pop(self.active_cfg)
            self.active_cfg = None

        if self.active_cfg:
            return self.async_show_form(
                step_id="options_digital",
                data_schema=vol.Schema(DATA_SCHEMA_SENSOR_OPTIONS),
                description_placeholders={
                    "zone": "Zone " + self.active_cfg
                    if len(self.active_cfg) < 3
                    else self.active_cfg.upper()
                },
                errors=errors,
            )

        # find the next unconfigured binary sensor
        for key, value in self.io_cfg.items():
            if value == "Digital Sensor":
                self.active_cfg = key
                return self.async_show_form(
                    step_id="options_digital",
                    data_schema=vol.Schema(DATA_SCHEMA_SENSOR_OPTIONS),
                    description_placeholders={
                        "zone": "Zone " + self.active_cfg
                        if len(self.active_cfg) < 3
                        else self.active_cfg.upper()
                    },
                    errors=errors,
                )

        return await self.async_step_options_switch()

    async def async_step_options_switch(self, user_input=None):
        """Allow the user to configure the IO options for switches."""
        errors = {}
        if user_input is not None:
            zone = {"zone": self.active_cfg}
            zone.update(user_input)
            self.switches.append(zone)
            self.io_cfg.pop(self.active_cfg)
            self.active_cfg = None

        if self.active_cfg:
            return self.async_show_form(
                step_id="options_switch",
                data_schema=vol.Schema(DATA_SCHEMA_SWITCH_OPTIONS),
                description_placeholders={
                    "zone": "Zone " + self.active_cfg
                    if len(self.active_cfg) < 3
                    else self.active_cfg.upper()
                },
                errors=errors,
            )

        # find the next unconfigured binary sensor
        for key, value in self.io_cfg.items():
            if value == "Switchable Output":
                self.active_cfg = key
                return self.async_show_form(
                    step_id="options_switch",
                    data_schema=vol.Schema(DATA_SCHEMA_SWITCH_OPTIONS),
                    description_placeholders={
                        "zone": "Zone " + self.active_cfg
                        if len(self.active_cfg) < 3
                        else self.active_cfg.upper()
                    },
                    errors=errors,
                )

        # Build a config mimicking configuration.yaml
        return await self.async_create_or_update_entry(
            {
                "host": self.host,
                "port": self.port,
                "id": self.device_id,
                "binary_sensors": self.binary_sensors,
                "sensors": self.sensors,
                "switches": self.switches,
            }
        )

    async def async_create_or_update_entry(self, device_config):
        """Create or update a config entry based on the config flow info.

        If an existing config entry is found, we will validate the info
        and replace the entry. Otherwise we will create a new one.
        """
        try:
            device_config = DEVICE_SCHEMA(device_config)

        except vol.Invalid as err:
            _LOGGER.error(
                "Invalid device config..%s", humanize_error(device_config, err),
            )
            return self.async_abort(reason="unknown")

        # Remove all other entries of panels with same ID or host
        same_panel_entries = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data[CONF_ID] == device_config[CONF_ID]
            or entry.data[CONF_HOST] == device_config[CONF_HOST]
        ]

        if same_panel_entries:
            await asyncio.wait(
                [
                    self.hass.config_entries.async_remove(entry_id)
                    for entry_id in same_panel_entries
                ]
            )

        # remove any cached data and make the entry
        if self.cached_config:
            self.hass.data[DOMAIN]["config_data"].pop(self.device_id, None)

        return self.async_create_entry(
            title=KONN_PANEL_MODEL_NAMES[self.model], data=device_config,
        )
