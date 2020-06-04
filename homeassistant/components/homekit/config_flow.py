"""Config flow for HomeKit integration."""
import logging
import random
import string

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import callback, split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
)

from .const import (
    CONF_AUTO_START,
    CONF_ENTITY_CONFIG,
    CONF_FILTER,
    CONF_SAFE_MODE,
    CONF_VIDEO_CODEC,
    DEFAULT_AUTO_START,
    DEFAULT_CONFIG_FLOW_PORT,
    DEFAULT_SAFE_MODE,
    SHORT_BRIDGE_NAME,
    VIDEO_CODEC_COPY,
)
from .const import DOMAIN  # pylint:disable=unused-import
from .util import find_next_available_port

_LOGGER = logging.getLogger(__name__)

CONF_CAMERA_COPY = "camera_copy"
CONF_DOMAINS = "domains"

SUPPORTED_DOMAINS = [
    "alarm_control_panel",
    "automation",
    "binary_sensor",
    "camera",
    "climate",
    "cover",
    "demo",
    "device_tracker",
    "fan",
    "input_boolean",
    "light",
    "lock",
    "media_player",
    "person",
    "remote",
    "scene",
    "script",
    "sensor",
    "switch",
    "vacuum",
    "water_heater",
]

DEFAULT_DOMAINS = [
    "alarm_control_panel",
    "climate",
    "cover",
    "light",
    "lock",
    "media_player",
    "switch",
    "vacuum",
    "water_heater",
]


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomeKit."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize config flow."""
        self.homekit_data = {}
        self.entry_title = None

    async def async_step_pairing(self, user_input=None):
        """Pairing instructions."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.entry_title, data=self.homekit_data
            )
        return self.async_show_form(
            step_id="pairing",
            description_placeholders={CONF_NAME: self.homekit_data[CONF_NAME]},
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            port = await self._async_available_port()
            name = self._async_available_name()
            title = f"{name}:{port}"
            self.homekit_data = user_input.copy()
            self.homekit_data[CONF_NAME] = name
            self.homekit_data[CONF_PORT] = port
            self.homekit_data[CONF_FILTER] = {
                CONF_INCLUDE_DOMAINS: user_input[CONF_INCLUDE_DOMAINS],
                CONF_INCLUDE_ENTITIES: [],
                CONF_EXCLUDE_DOMAINS: [],
                CONF_EXCLUDE_ENTITIES: [],
            }
            del self.homekit_data[CONF_INCLUDE_DOMAINS]
            self.entry_title = title
            return await self.async_step_pairing()

        default_domains = [] if self._async_current_entries() else DEFAULT_DOMAINS
        setup_schema = vol.Schema(
            {
                vol.Optional(CONF_AUTO_START, default=DEFAULT_AUTO_START): bool,
                vol.Required(
                    CONF_INCLUDE_DOMAINS, default=default_domains
                ): cv.multi_select(SUPPORTED_DOMAINS),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=setup_schema, errors=errors
        )

    async def async_step_import(self, user_input=None):
        """Handle import from yaml."""
        if not self._async_is_unique_name_port(user_input):
            return self.async_abort(reason="port_name_in_use")
        return self.async_create_entry(
            title=f"{user_input[CONF_NAME]}:{user_input[CONF_PORT]}", data=user_input
        )

    async def _async_available_port(self):
        """Return an available port the bridge."""
        return await self.hass.async_add_executor_job(
            find_next_available_port, DEFAULT_CONFIG_FLOW_PORT
        )

    @callback
    def _async_available_name(self):
        """Return an available for the bridge."""
        current_entries = self._async_current_entries()

        # We always pick a RANDOM name to avoid Zeroconf
        # name collisions.  If the name has been seen before
        # pairing will probably fail.
        acceptable_chars = string.ascii_uppercase + string.digits
        trailer = "".join(random.choices(acceptable_chars, k=4))
        all_names = {entry.data[CONF_NAME] for entry in current_entries}
        suggested_name = f"{SHORT_BRIDGE_NAME} {trailer}"
        while suggested_name in all_names:
            trailer = "".join(random.choices(acceptable_chars, k=4))
            suggested_name = f"{SHORT_BRIDGE_NAME} {trailer}"

        return suggested_name

    @callback
    def _async_is_unique_name_port(self, user_input):
        """Determine is a name or port is already used."""
        name = user_input[CONF_NAME]
        port = user_input[CONF_PORT]
        for entry in self._async_current_entries():
            if entry.data[CONF_NAME] == name or entry.data[CONF_PORT] == port:
                return False
        return True

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for tado."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.homekit_options = {}
        self.included_cameras = set()

    async def async_step_yaml(self, user_input=None):
        """No options for yaml managed entries."""
        if user_input is not None:
            # Apparently not possible to abort an options flow
            # at the moment
            return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(step_id="yaml")

    async def async_step_advanced(self, user_input=None):
        """Choose advanced options."""
        if user_input is not None:
            self.homekit_options.update(user_input)
            del self.homekit_options[CONF_INCLUDE_DOMAINS]
            return self.async_create_entry(title="", data=self.homekit_options)

        schema_base = {}

        if self.show_advanced_options:
            schema_base[
                vol.Optional(
                    CONF_AUTO_START,
                    default=self.homekit_options.get(
                        CONF_AUTO_START, DEFAULT_AUTO_START
                    ),
                )
            ] = bool
        else:
            self.homekit_options[CONF_AUTO_START] = self.homekit_options.get(
                CONF_AUTO_START, DEFAULT_AUTO_START
            )

        schema_base.update(
            {
                vol.Optional(
                    CONF_SAFE_MODE,
                    default=self.homekit_options.get(CONF_SAFE_MODE, DEFAULT_SAFE_MODE),
                ): bool
            }
        )

        return self.async_show_form(
            step_id="advanced", data_schema=vol.Schema(schema_base)
        )

    async def async_step_cameras(self, user_input=None):
        """Choose camera config."""
        if user_input is not None:
            entity_config = self.homekit_options[CONF_ENTITY_CONFIG]
            for entity_id in self.included_cameras:
                if entity_id in user_input[CONF_CAMERA_COPY]:
                    entity_config.setdefault(entity_id, {})[
                        CONF_VIDEO_CODEC
                    ] = VIDEO_CODEC_COPY
                elif (
                    entity_id in entity_config
                    and CONF_VIDEO_CODEC in entity_config[entity_id]
                ):
                    del entity_config[entity_id][CONF_VIDEO_CODEC]
            return await self.async_step_advanced()

        cameras_with_copy = []
        entity_config = self.homekit_options.setdefault(CONF_ENTITY_CONFIG, {})
        for entity in self.included_cameras:
            hk_entity_config = entity_config.get(entity, {})
            if hk_entity_config.get(CONF_VIDEO_CODEC) == VIDEO_CODEC_COPY:
                cameras_with_copy.append(entity)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CAMERA_COPY, default=cameras_with_copy,
                ): cv.multi_select(self.included_cameras),
            }
        )
        return self.async_show_form(step_id="cameras", data_schema=data_schema)

    async def async_step_exclude(self, user_input=None):
        """Choose entities to exclude from the domain."""
        if user_input is not None:
            self.homekit_options[CONF_FILTER] = {
                CONF_INCLUDE_DOMAINS: self.homekit_options[CONF_INCLUDE_DOMAINS],
                CONF_EXCLUDE_DOMAINS: self.homekit_options.get(
                    CONF_EXCLUDE_DOMAINS, []
                ),
                CONF_INCLUDE_ENTITIES: self.homekit_options.get(
                    CONF_INCLUDE_ENTITIES, []
                ),
                CONF_EXCLUDE_ENTITIES: user_input[CONF_EXCLUDE_ENTITIES],
            }
            for entity_id in user_input[CONF_EXCLUDE_ENTITIES]:
                if entity_id in self.included_cameras:
                    self.included_cameras.remove(entity_id)
            if self.included_cameras:
                return await self.async_step_cameras()
            return await self.async_step_advanced()

        entity_filter = self.homekit_options.get(CONF_FILTER, {})
        all_supported_entities = await self.hass.async_add_executor_job(
            _get_entities_matching_domains,
            self.hass,
            self.homekit_options[CONF_INCLUDE_DOMAINS],
        )
        self.included_cameras = {
            entity_id
            for entity_id in all_supported_entities
            if entity_id.startswith("camera.")
        }
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EXCLUDE_ENTITIES,
                    default=entity_filter.get(CONF_EXCLUDE_ENTITIES, []),
                ): cv.multi_select(all_supported_entities),
            }
        )
        return self.async_show_form(step_id="exclude", data_schema=data_schema)

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if self.config_entry.source == SOURCE_IMPORT:
            return await self.async_step_yaml(user_input)

        if user_input is not None:
            self.homekit_options.update(user_input)
            return await self.async_step_exclude()

        self.homekit_options = dict(self.config_entry.options)
        entity_filter = self.homekit_options.get(CONF_FILTER, {})

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_INCLUDE_DOMAINS,
                    default=entity_filter.get(CONF_INCLUDE_DOMAINS, []),
                ): cv.multi_select(SUPPORTED_DOMAINS)
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


def _get_entities_matching_domains(hass, domains):
    """List entities in the given domains."""
    included_domains = set(domains)
    entity_ids = [
        state.entity_id
        for state in hass.states.all()
        if (split_entity_id(state.entity_id))[0] in included_domains
    ]
    entity_ids.sort()
    return entity_ids
