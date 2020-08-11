"""Config flow for konnected.io integration."""
import asyncio
import copy
import logging
import random
import string
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.ssdp import ATTR_UPNP_MANUFACTURER, ATTR_UPNP_MODEL_NAME
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
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
    CONF_API_HOST,
    CONF_BLINK,
    CONF_DEFAULT_OPTIONS,
    CONF_DISCOVERY,
    CONF_INVERSE,
    CONF_MODEL,
    CONF_MOMENTARY,
    CONF_PAUSE,
    CONF_POLL_INTERVAL,
    CONF_REPEAT,
    DOMAIN,
    STATE_HIGH,
    STATE_LOW,
    ZONES,
)
from .errors import CannotConnect
from .panel import KONN_MODEL, KONN_MODEL_PRO, get_status

_LOGGER = logging.getLogger(__name__)

ATTR_KONN_UPNP_MODEL_NAME = "model_name"  # standard upnp is modelName
CONF_IO = "io"
CONF_IO_DIS = "Disabled"
CONF_IO_BIN = "Binary Sensor"
CONF_IO_DIG = "Digital Sensor"
CONF_IO_SWI = "Switchable Output"

CONF_MORE_STATES = "more_states"
CONF_YES = "Yes"
CONF_NO = "No"

CONF_OVERRIDE_API_HOST = "override_api_host"

KONN_MANUFACTURER = "konnected.io"
KONN_PANEL_MODEL_NAMES = {
    KONN_MODEL: "Konnected Alarm Panel",
    KONN_MODEL_PRO: "Konnected Alarm Panel Pro",
}

OPTIONS_IO_ANY = vol.In([CONF_IO_DIS, CONF_IO_BIN, CONF_IO_DIG, CONF_IO_SWI])
OPTIONS_IO_INPUT_ONLY = vol.In([CONF_IO_DIS, CONF_IO_BIN, CONF_IO_DIG])
OPTIONS_IO_OUTPUT_ONLY = vol.In([CONF_IO_DIS, CONF_IO_SWI])


# Config entry schemas
IO_SCHEMA = vol.Schema(
    {
        vol.Optional("1", default=CONF_IO_DIS): OPTIONS_IO_ANY,
        vol.Optional("2", default=CONF_IO_DIS): OPTIONS_IO_ANY,
        vol.Optional("3", default=CONF_IO_DIS): OPTIONS_IO_ANY,
        vol.Optional("4", default=CONF_IO_DIS): OPTIONS_IO_ANY,
        vol.Optional("5", default=CONF_IO_DIS): OPTIONS_IO_ANY,
        vol.Optional("6", default=CONF_IO_DIS): OPTIONS_IO_ANY,
        vol.Optional("7", default=CONF_IO_DIS): OPTIONS_IO_ANY,
        vol.Optional("8", default=CONF_IO_DIS): OPTIONS_IO_ANY,
        vol.Optional("9", default=CONF_IO_DIS): OPTIONS_IO_INPUT_ONLY,
        vol.Optional("10", default=CONF_IO_DIS): OPTIONS_IO_INPUT_ONLY,
        vol.Optional("11", default=CONF_IO_DIS): OPTIONS_IO_INPUT_ONLY,
        vol.Optional("12", default=CONF_IO_DIS): OPTIONS_IO_INPUT_ONLY,
        vol.Optional("out", default=CONF_IO_DIS): OPTIONS_IO_OUTPUT_ONLY,
        vol.Optional("alarm1", default=CONF_IO_DIS): OPTIONS_IO_OUTPUT_ONLY,
        vol.Optional("out1", default=CONF_IO_DIS): OPTIONS_IO_OUTPUT_ONLY,
        vol.Optional("alarm2_out2", default=CONF_IO_DIS): OPTIONS_IO_OUTPUT_ONLY,
    }
)

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE): vol.In(ZONES),
        vol.Required(CONF_TYPE, default=DEVICE_CLASS_DOOR): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_INVERSE, default=False): cv.boolean,
    }
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE): vol.In(ZONES),
        vol.Required(CONF_TYPE, default="dht"): vol.All(
            vol.Lower, vol.In(["dht", "ds18b20"])
        ),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_POLL_INTERVAL, default=3): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
    }
)

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE): vol.In(ZONES),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ACTIVATION, default=STATE_HIGH): vol.All(
            vol.Lower, vol.In([STATE_HIGH, STATE_LOW])
        ),
        vol.Optional(CONF_MOMENTARY): vol.All(vol.Coerce(int), vol.Range(min=10)),
        vol.Optional(CONF_PAUSE): vol.All(vol.Coerce(int), vol.Range(min=10)),
        vol.Optional(CONF_REPEAT): vol.All(vol.Coerce(int), vol.Range(min=-1)),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IO): IO_SCHEMA,
        vol.Optional(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list, [BINARY_SENSOR_SCHEMA]
        ),
        vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [SENSOR_SCHEMA]),
        vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [SWITCH_SCHEMA]),
        vol.Optional(CONF_BLINK, default=True): cv.boolean,
        vol.Optional(CONF_API_HOST, default=""): vol.Any("", cv.url),
        vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
    },
    extra=vol.REMOVE_EXTRA,
)

CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.matches_regex("[0-9a-f]{12}"),
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_MODEL): vol.Any(*KONN_PANEL_MODEL_NAMES),
        vol.Required(CONF_ACCESS_TOKEN): cv.matches_regex("[a-zA-Z0-9]+"),
        vol.Required(CONF_DEFAULT_OPTIONS): OPTIONS_SCHEMA,
    },
    extra=vol.REMOVE_EXTRA,
)


class KonnectedFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NEW_NAME."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    # class variable to store/share discovered host information
    discovered_hosts = {}

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167

    def __init__(self):
        """Initialize the Konnected flow."""
        self.data = {}
        self.options = OPTIONS_SCHEMA({CONF_IO: {}})

    async def async_gen_config(self, host, port):
        """Populate self.data based on panel status.

        This will raise CannotConnect if an error occurs
        """
        self.data[CONF_HOST] = host
        self.data[CONF_PORT] = port
        try:
            status = await get_status(self.hass, host, port)
            self.data[CONF_ID] = status.get("chipId", status["mac"].replace(":", ""))
        except (CannotConnect, KeyError):
            raise CannotConnect
        else:
            self.data[CONF_MODEL] = status.get("model", KONN_MODEL)
            self.data[CONF_ACCESS_TOKEN] = "".join(
                random.choices(f"{string.ascii_uppercase}{string.digits}", k=20)
            )

    async def async_step_import(self, device_config):
        """Import a configuration.yaml config.

        This flow is triggered by `async_setup` for configured panels.
        """
        _LOGGER.debug(device_config)

        # save the data and confirm connection via user step
        await self.async_set_unique_id(device_config["id"])
        self.options = device_config[CONF_DEFAULT_OPTIONS]

        # config schema ensures we have port if we have host
        if device_config.get(CONF_HOST):
            # automatically connect if we have host info
            return await self.async_step_user(
                user_input={
                    CONF_HOST: device_config[CONF_HOST],
                    CONF_PORT: device_config[CONF_PORT],
                }
            )

        # if we have no host info wait for it or abort if previously configured
        self._abort_if_unique_id_configured()
        return await self.async_step_import_confirm()

    async def async_step_import_confirm(self, user_input=None):
        """Confirm the user wants to import the config entry."""
        if user_input is None:
            return self.async_show_form(
                step_id="import_confirm",
                description_placeholders={"id": self.unique_id},
            )

        # if we have ssdp discovered applicable host info use it
        if KonnectedFlowHandler.discovered_hosts.get(self.unique_id):
            return await self.async_step_user(
                user_input={
                    CONF_HOST: KonnectedFlowHandler.discovered_hosts[self.unique_id][
                        CONF_HOST
                    ],
                    CONF_PORT: KonnectedFlowHandler.discovered_hosts[self.unique_id][
                        CONF_PORT
                    ],
                }
            )
        return await self.async_step_user()

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered konnected panel.

        This flow is triggered by the SSDP component. It will check if the
        device is already configured and attempt to finish the config if not.
        """
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

        # If MAC is missing it is a bug in the device fw but we'll guard
        # against it since the field is so vital
        except KeyError:
            _LOGGER.error("Malformed Konnected SSDP info")
        else:
            # extract host/port from ssdp_location
            netloc = urlparse(discovery_info["ssdp_location"]).netloc.split(":")
            return await self.async_step_user(
                user_input={CONF_HOST: netloc[0], CONF_PORT: int(netloc[1])}
            )

        return self.async_abort(reason="unknown")

    async def async_step_user(self, user_input=None):
        """Connect to panel and get config."""
        errors = {}
        if user_input:
            # build config info and wait for user confirmation
            self.data[CONF_HOST] = user_input[CONF_HOST]
            self.data[CONF_PORT] = user_input[CONF_PORT]

            # brief delay to allow processing of recent status req
            await asyncio.sleep(0.1)
            try:
                status = await get_status(
                    self.hass, self.data[CONF_HOST], self.data[CONF_PORT]
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                self.data[CONF_ID] = status.get(
                    "chipId", status["mac"].replace(":", "")
                )
                self.data[CONF_MODEL] = status.get("model", KONN_MODEL)

                # save off our discovered host info
                KonnectedFlowHandler.discovered_hosts[self.data[CONF_ID]] = {
                    CONF_HOST: self.data[CONF_HOST],
                    CONF_PORT: self.data[CONF_PORT],
                }
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "host": self.data.get(CONF_HOST, "Unknown"),
                "port": self.data.get(CONF_PORT, "Unknown"),
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self.data.get(CONF_HOST)): str,
                    vol.Required(CONF_PORT, default=self.data.get(CONF_PORT)): int,
                }
            ),
            errors=errors,
        )

    async def async_step_confirm(self, user_input=None):
        """Attempt to link with the Konnected panel.

        Given a configured host, will ask the user to confirm and finalize
        the connection.
        """
        if user_input is None:
            # abort and update an existing config entry if host info changes
            await self.async_set_unique_id(self.data[CONF_ID])
            self._abort_if_unique_id_configured(
                updates=self.data, reload_on_update=False
            )
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "model": KONN_PANEL_MODEL_NAMES[self.data[CONF_MODEL]],
                    "id": self.unique_id,
                    "host": self.data[CONF_HOST],
                    "port": self.data[CONF_PORT],
                },
            )

        # Create access token, attach default options and create entry
        self.data[CONF_DEFAULT_OPTIONS] = self.options
        self.data[CONF_ACCESS_TOKEN] = self.hass.data.get(DOMAIN, {}).get(
            CONF_ACCESS_TOKEN
        ) or "".join(random.choices(f"{string.ascii_uppercase}{string.digits}", k=20))

        return self.async_create_entry(
            title=KONN_PANEL_MODEL_NAMES[self.data[CONF_MODEL]], data=self.data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the Options Flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for a Konnected Panel."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.entry = config_entry
        self.model = self.entry.data[CONF_MODEL]
        self.current_opt = self.entry.options or self.entry.data[CONF_DEFAULT_OPTIONS]

        # as config proceeds we'll build up new options and then replace what's in the config entry
        self.new_opt = {CONF_IO: {}}
        self.active_cfg = None
        self.io_cfg = {}
        self.current_states = []
        self.current_state = 1

    @callback
    def get_current_cfg(self, io_type, zone):
        """Get the current zone config."""
        return next(
            (
                cfg
                for cfg in self.current_opt.get(io_type, [])
                if cfg[CONF_ZONE] == zone
            ),
            {},
        )

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        return await self.async_step_options_io()

    async def async_step_options_io(self, user_input=None):
        """Configure legacy panel IO or first half of pro IO."""
        errors = {}
        current_io = self.current_opt.get(CONF_IO, {})

        if user_input is not None:
            # strip out disabled io and save for options cfg
            for key, value in user_input.items():
                if value != CONF_IO_DIS:
                    self.new_opt[CONF_IO][key] = value
            return await self.async_step_options_io_ext()

        if self.model == KONN_MODEL:
            return self.async_show_form(
                step_id="options_io",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "1", default=current_io.get("1", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "2", default=current_io.get("2", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "3", default=current_io.get("3", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "4", default=current_io.get("4", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "5", default=current_io.get("5", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "6", default=current_io.get("6", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "out", default=current_io.get("out", CONF_IO_DIS)
                        ): OPTIONS_IO_OUTPUT_ONLY,
                    }
                ),
                description_placeholders={
                    "model": KONN_PANEL_MODEL_NAMES[self.model],
                    "host": self.entry.data[CONF_HOST],
                },
                errors=errors,
            )

        # configure the first half of the pro board io
        if self.model == KONN_MODEL_PRO:
            return self.async_show_form(
                step_id="options_io",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "1", default=current_io.get("1", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "2", default=current_io.get("2", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "3", default=current_io.get("3", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "4", default=current_io.get("4", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "5", default=current_io.get("5", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "6", default=current_io.get("6", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "7", default=current_io.get("7", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                    }
                ),
                description_placeholders={
                    "model": KONN_PANEL_MODEL_NAMES[self.model],
                    "host": self.entry.data[CONF_HOST],
                },
                errors=errors,
            )

        return self.async_abort(reason="not_konn_panel")

    async def async_step_options_io_ext(self, user_input=None):
        """Allow the user to configure the extended IO for pro."""
        errors = {}
        current_io = self.current_opt.get(CONF_IO, {})

        if user_input is not None:
            # strip out disabled io and save for options cfg
            for key, value in user_input.items():
                if value != CONF_IO_DIS:
                    self.new_opt[CONF_IO].update({key: value})
            self.io_cfg = copy.deepcopy(self.new_opt[CONF_IO])
            return await self.async_step_options_binary()

        if self.model == KONN_MODEL:
            self.io_cfg = copy.deepcopy(self.new_opt[CONF_IO])
            return await self.async_step_options_binary()

        if self.model == KONN_MODEL_PRO:
            return self.async_show_form(
                step_id="options_io_ext",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "8", default=current_io.get("8", CONF_IO_DIS)
                        ): OPTIONS_IO_ANY,
                        vol.Required(
                            "9", default=current_io.get("9", CONF_IO_DIS)
                        ): OPTIONS_IO_INPUT_ONLY,
                        vol.Required(
                            "10", default=current_io.get("10", CONF_IO_DIS)
                        ): OPTIONS_IO_INPUT_ONLY,
                        vol.Required(
                            "11", default=current_io.get("11", CONF_IO_DIS)
                        ): OPTIONS_IO_INPUT_ONLY,
                        vol.Required(
                            "12", default=current_io.get("12", CONF_IO_DIS)
                        ): OPTIONS_IO_INPUT_ONLY,
                        vol.Required(
                            "alarm1", default=current_io.get("alarm1", CONF_IO_DIS)
                        ): OPTIONS_IO_OUTPUT_ONLY,
                        vol.Required(
                            "out1", default=current_io.get("out1", CONF_IO_DIS)
                        ): OPTIONS_IO_OUTPUT_ONLY,
                        vol.Required(
                            "alarm2_out2",
                            default=current_io.get("alarm2_out2", CONF_IO_DIS),
                        ): OPTIONS_IO_OUTPUT_ONLY,
                    }
                ),
                description_placeholders={
                    "model": KONN_PANEL_MODEL_NAMES[self.model],
                    "host": self.entry.data[CONF_HOST],
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
            self.new_opt[CONF_BINARY_SENSORS] = self.new_opt.get(
                CONF_BINARY_SENSORS, []
            ) + [zone]
            self.io_cfg.pop(self.active_cfg)
            self.active_cfg = None

        if self.active_cfg:
            current_cfg = self.get_current_cfg(CONF_BINARY_SENSORS, self.active_cfg)
            return self.async_show_form(
                step_id="options_binary",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_TYPE,
                            default=current_cfg.get(CONF_TYPE, DEVICE_CLASS_DOOR),
                        ): DEVICE_CLASSES_SCHEMA,
                        vol.Optional(
                            CONF_NAME, default=current_cfg.get(CONF_NAME, vol.UNDEFINED)
                        ): str,
                        vol.Optional(
                            CONF_INVERSE, default=current_cfg.get(CONF_INVERSE, False)
                        ): bool,
                    }
                ),
                description_placeholders={
                    "zone": f"Zone {self.active_cfg}"
                    if len(self.active_cfg) < 3
                    else self.active_cfg.upper
                },
                errors=errors,
            )

        # find the next unconfigured binary sensor
        for key, value in self.io_cfg.items():
            if value == CONF_IO_BIN:
                self.active_cfg = key
                current_cfg = self.get_current_cfg(CONF_BINARY_SENSORS, self.active_cfg)
                return self.async_show_form(
                    step_id="options_binary",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_TYPE,
                                default=current_cfg.get(CONF_TYPE, DEVICE_CLASS_DOOR),
                            ): DEVICE_CLASSES_SCHEMA,
                            vol.Optional(
                                CONF_NAME,
                                default=current_cfg.get(CONF_NAME, vol.UNDEFINED),
                            ): str,
                            vol.Optional(
                                CONF_INVERSE,
                                default=current_cfg.get(CONF_INVERSE, False),
                            ): bool,
                        }
                    ),
                    description_placeholders={
                        "zone": f"Zone {self.active_cfg}"
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
            self.new_opt[CONF_SENSORS] = self.new_opt.get(CONF_SENSORS, []) + [zone]
            self.io_cfg.pop(self.active_cfg)
            self.active_cfg = None

        if self.active_cfg:
            current_cfg = self.get_current_cfg(CONF_SENSORS, self.active_cfg)
            return self.async_show_form(
                step_id="options_digital",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_TYPE, default=current_cfg.get(CONF_TYPE, "dht")
                        ): vol.All(vol.Lower, vol.In(["dht", "ds18b20"])),
                        vol.Optional(
                            CONF_NAME, default=current_cfg.get(CONF_NAME, vol.UNDEFINED)
                        ): str,
                        vol.Optional(
                            CONF_POLL_INTERVAL,
                            default=current_cfg.get(CONF_POLL_INTERVAL, 3),
                        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                    }
                ),
                description_placeholders={
                    "zone": f"Zone {self.active_cfg}"
                    if len(self.active_cfg) < 3
                    else self.active_cfg.upper()
                },
                errors=errors,
            )

        # find the next unconfigured digital sensor
        for key, value in self.io_cfg.items():
            if value == CONF_IO_DIG:
                self.active_cfg = key
                current_cfg = self.get_current_cfg(CONF_SENSORS, self.active_cfg)
                return self.async_show_form(
                    step_id="options_digital",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_TYPE, default=current_cfg.get(CONF_TYPE, "dht")
                            ): vol.All(vol.Lower, vol.In(["dht", "ds18b20"])),
                            vol.Optional(
                                CONF_NAME,
                                default=current_cfg.get(CONF_NAME, vol.UNDEFINED),
                            ): str,
                            vol.Optional(
                                CONF_POLL_INTERVAL,
                                default=current_cfg.get(CONF_POLL_INTERVAL, 3),
                            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                        }
                    ),
                    description_placeholders={
                        "zone": f"Zone {self.active_cfg}"
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
            del zone[CONF_MORE_STATES]
            self.new_opt[CONF_SWITCHES] = self.new_opt.get(CONF_SWITCHES, []) + [zone]

            # iterate through multiple switch states
            if self.current_states:
                self.current_states.pop(0)

            # only go to next zone if all states are entered
            self.current_state += 1
            if user_input[CONF_MORE_STATES] == CONF_NO:
                self.io_cfg.pop(self.active_cfg)
                self.active_cfg = None

        if self.active_cfg:
            current_cfg = next(iter(self.current_states), {})
            return self.async_show_form(
                step_id="options_switch",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_NAME, default=current_cfg.get(CONF_NAME, vol.UNDEFINED)
                        ): str,
                        vol.Optional(
                            CONF_ACTIVATION,
                            default=current_cfg.get(CONF_ACTIVATION, STATE_HIGH),
                        ): vol.All(vol.Lower, vol.In([STATE_HIGH, STATE_LOW])),
                        vol.Optional(
                            CONF_MOMENTARY,
                            default=current_cfg.get(CONF_MOMENTARY, vol.UNDEFINED),
                        ): vol.All(vol.Coerce(int), vol.Range(min=10)),
                        vol.Optional(
                            CONF_PAUSE,
                            default=current_cfg.get(CONF_PAUSE, vol.UNDEFINED),
                        ): vol.All(vol.Coerce(int), vol.Range(min=10)),
                        vol.Optional(
                            CONF_REPEAT,
                            default=current_cfg.get(CONF_REPEAT, vol.UNDEFINED),
                        ): vol.All(vol.Coerce(int), vol.Range(min=-1)),
                        vol.Required(
                            CONF_MORE_STATES,
                            default=CONF_YES
                            if len(self.current_states) > 1
                            else CONF_NO,
                        ): vol.In([CONF_YES, CONF_NO]),
                    }
                ),
                description_placeholders={
                    "zone": f"Zone {self.active_cfg}"
                    if len(self.active_cfg) < 3
                    else self.active_cfg.upper(),
                    "state": str(self.current_state),
                },
                errors=errors,
            )

        # find the next unconfigured switch
        for key, value in self.io_cfg.items():
            if value == CONF_IO_SWI:
                self.active_cfg = key
                self.current_states = [
                    cfg
                    for cfg in self.current_opt.get(CONF_SWITCHES, [])
                    if cfg[CONF_ZONE] == self.active_cfg
                ]
                current_cfg = next(iter(self.current_states), {})
                self.current_state = 1
                return self.async_show_form(
                    step_id="options_switch",
                    data_schema=vol.Schema(
                        {
                            vol.Optional(
                                CONF_NAME,
                                default=current_cfg.get(CONF_NAME, vol.UNDEFINED),
                            ): str,
                            vol.Optional(
                                CONF_ACTIVATION,
                                default=current_cfg.get(CONF_ACTIVATION, STATE_HIGH),
                            ): vol.In(["low", "high"]),
                            vol.Optional(
                                CONF_MOMENTARY,
                                default=current_cfg.get(CONF_MOMENTARY, vol.UNDEFINED),
                            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
                            vol.Optional(
                                CONF_PAUSE,
                                default=current_cfg.get(CONF_PAUSE, vol.UNDEFINED),
                            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
                            vol.Optional(
                                CONF_REPEAT,
                                default=current_cfg.get(CONF_REPEAT, vol.UNDEFINED),
                            ): vol.All(vol.Coerce(int), vol.Range(min=-1)),
                            vol.Required(
                                CONF_MORE_STATES,
                                default=CONF_YES
                                if len(self.current_states) > 1
                                else CONF_NO,
                            ): vol.In([CONF_YES, CONF_NO]),
                        }
                    ),
                    description_placeholders={
                        "zone": f"Zone {self.active_cfg}"
                        if len(self.active_cfg) < 3
                        else self.active_cfg.upper(),
                        "state": str(self.current_state),
                    },
                    errors=errors,
                )

        return await self.async_step_options_misc()

    async def async_step_options_misc(self, user_input=None):
        """Allow the user to configure the LED behavior."""
        errors = {}
        if user_input is not None:
            # config schema only does basic schema val so check url here
            try:
                if user_input[CONF_OVERRIDE_API_HOST]:
                    cv.url(user_input.get(CONF_API_HOST, ""))
                else:
                    user_input[CONF_API_HOST] = ""
            except vol.Invalid:
                errors["base"] = "bad_host"
            else:
                # no need to store the override - can infer
                del user_input[CONF_OVERRIDE_API_HOST]
                self.new_opt.update(user_input)
                return self.async_create_entry(title="", data=self.new_opt)

        return self.async_show_form(
            step_id="options_misc",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BLINK, default=self.current_opt.get(CONF_BLINK, True)
                    ): bool,
                    vol.Required(
                        CONF_OVERRIDE_API_HOST,
                        default=bool(self.current_opt.get(CONF_API_HOST)),
                    ): bool,
                    vol.Optional(
                        CONF_API_HOST, default=self.current_opt.get(CONF_API_HOST, "")
                    ): str,
                }
            ),
            errors=errors,
        )
