"""Config flow for Somfy MyLink integration."""
import asyncio
import logging

from somfy_mylink_synergy import SomfyMyLinkSynergy
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_ENTITY_ID, CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import (
    CONF_DEFAULT_REVERSE,
    CONF_ENTITY_CONFIG,
    CONF_REVERSE,
    CONF_SYSTEM_ID,
    DEFAULT_CONF_DEFAULT_REVERSE,
    DEFAULT_PORT,
    MYLINK_ENTITY_IDS,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

ENTITY_CONFIG_VERSION = "entity_config_version"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_SYSTEM_ID): int,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    somfy_mylink = SomfyMyLinkSynergy(
        data[CONF_SYSTEM_ID], data[CONF_HOST], data[CONF_PORT]
    )

    try:
        status_info = await somfy_mylink.status_info()
    except asyncio.TimeoutError as ex:
        raise CannotConnect from ex

    if not status_info or "error" in status_info:
        raise InvalidAuth

    return {"title": f"MyLink {data[CONF_HOST]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Somfy MyLink."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_ASSUMED

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        if self._host_already_configured(user_input[CONF_HOST]):
            return self.async_abort(reason="already_configured")

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        if self._host_already_configured(user_input[CONF_HOST]):
            return self.async_abort(reason="already_configured")

        return await self.async_step_user(user_input)

    def _host_already_configured(self, host):
        """See if we already have an entry matching the host."""
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == host:
                return True
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for somfy_mylink."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = config_entry.options.copy()
        self._entity_id = None

    async def async_step_init(self, user_input=None):
        """Handle options flow."""

        if self.config_entry.state != config_entries.ENTRY_STATE_LOADED:
            _LOGGER.error("MyLink must be connected to manage device options")
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            self.options[CONF_DEFAULT_REVERSE] = user_input[CONF_DEFAULT_REVERSE]

            entity_id = user_input.get(CONF_ENTITY_ID)
            if entity_id:
                return await self.async_step_entity_config(None, entity_id)

            return self.async_create_entry(title="", data=self.options)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEFAULT_REVERSE,
                    default=self.options.get(
                        CONF_DEFAULT_REVERSE, DEFAULT_CONF_DEFAULT_REVERSE
                    ),
                ): bool
            }
        )
        data = self.hass.data[DOMAIN][self.config_entry.entry_id]
        mylink_entity_ids = data[MYLINK_ENTITY_IDS]

        if mylink_entity_ids:
            entity_dict = {None: None}
            for entity_id in mylink_entity_ids:
                name = entity_id
                state = self.hass.states.get(entity_id)
                if state:
                    name = state.attributes.get(ATTR_FRIENDLY_NAME, entity_id)
                entity_dict[entity_id] = f"{name} ({entity_id})"
            data_schema = data_schema.extend(
                {vol.Optional(CONF_ENTITY_ID): vol.In(entity_dict)}
            )

        return self.async_show_form(step_id="init", data_schema=data_schema, errors={})

    async def async_step_entity_config(self, user_input=None, entity_id=None):
        """Handle options flow for entity."""
        entities_config = self.options.setdefault(CONF_ENTITY_CONFIG, {})

        if user_input is not None:
            entity_config = entities_config.setdefault(self._entity_id, {})
            if entity_config.get(CONF_REVERSE) != user_input[CONF_REVERSE]:
                entity_config[CONF_REVERSE] = user_input[CONF_REVERSE]
                # If we do not modify a top level key
                # the entity config will never be written
                self.options.setdefault(ENTITY_CONFIG_VERSION, 0)
                self.options[ENTITY_CONFIG_VERSION] += 1
            return await self.async_step_init()

        self._entity_id = entity_id
        default_reverse = self.options.get(CONF_DEFAULT_REVERSE, False)
        entity_config = entities_config.get(entity_id, {})

        return self.async_show_form(
            step_id="entity_config",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_REVERSE,
                        default=entity_config.get(CONF_REVERSE, default_reverse),
                    ): bool
                }
            ),
            description_placeholders={
                CONF_ENTITY_ID: entity_id,
            },
            errors={},
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
