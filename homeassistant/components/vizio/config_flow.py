"""Config flow for Vizio."""
import logging
from typing import Any, Dict

from pyvizio import VizioAsync, async_guess_device_type
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DEVICE_CLASS_SPEAKER, DEVICE_CLASS_TV
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.core import callback

from . import validate_auth
from .const import (
    CONF_VOLUME_STEP,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _get_config_flow_schema(input_dict: Dict[str, Any] = None) -> vol.Schema:
    """Return schema defaults based on user input/config dict. Retain info already provided for future form views by setting them as defaults in schema."""
    if input_dict is None:
        input_dict = {}

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=input_dict.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            vol.Required(CONF_HOST, default=input_dict.get(CONF_HOST)): str,
            vol.Optional(
                CONF_DEVICE_CLASS,
                default=input_dict.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
            ): vol.All(str, vol.Lower, vol.In([DEVICE_CLASS_TV, DEVICE_CLASS_SPEAKER])),
            vol.Optional(
                CONF_ACCESS_TOKEN, default=input_dict.get(CONF_ACCESS_TOKEN, "")
            ): str,
        },
        extra=vol.REMOVE_EXTRA,
    )


def _host_is_same(host1: str, host2: str) -> bool:
    """Check if host1 and host2 are the same."""
    return host1.split(":")[0] == host2.split(":")[0]


class VizioOptionsConfigFlow(config_entries.OptionsFlow):
    """Handle Transmission client options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize vizio options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Manage the vizio options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_VOLUME_STEP,
                default=self.config_entry.options.get(
                    CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10))
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class VizioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Vizio config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> VizioOptionsConfigFlow:
        """Get the options flow for this handler."""
        return VizioOptionsConfigFlow(config_entry)

    def __init__(self) -> None:
        """Initialize config flow."""
        self._user_schema = None
        self._must_show_form = None

    async def async_step_user(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            # Store current values in case setup fails and user needs to edit
            self._user_schema = _get_config_flow_schema(user_input)

            # Check if new config entry matches any existing config entries
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if _host_is_same(entry.data[CONF_HOST], user_input[CONF_HOST]):
                    errors[CONF_HOST] = "host_exists"
                    break

                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break

            if not errors:
                try:
                    # Ensure schema passes custom validation, otherwise catch exception and add error
                    validate_auth(user_input)

                    # Ensure config is valid for a device
                    if not await VizioAsync.validate_ha_config(
                        user_input[CONF_HOST],
                        user_input.get(CONF_ACCESS_TOKEN),
                        user_input[CONF_DEVICE_CLASS],
                    ):
                        errors["base"] = "cant_connect"
                except vol.Invalid:
                    errors["base"] = "tv_needs_token"

            if not errors:
                # Skip validating config and creating entry if form must be shown
                if self._must_show_form:
                    self._must_show_form = False
                else:
                    # Abort flow if existing entry with same unique ID matches new config entry.
                    # Since name and host check have already passed, if an entry already exists,
                    # It is likely a reconfigured device.
                    unique_id = await VizioAsync.get_unique_id(
                        user_input[CONF_HOST],
                        user_input.get(CONF_ACCESS_TOKEN),
                        user_input[CONF_DEVICE_CLASS],
                    )

                    if await self.async_set_unique_id(
                        unique_id=unique_id, raise_on_progress=True
                    ):
                        return self.async_abort(
                            reason="already_setup_with_diff_host_and_name"
                        )

                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data=user_input
                    )

        # Use user_input params as default values for schema if user_input is non-empty, otherwise use default schema
        schema = self._user_schema or _get_config_flow_schema()

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, import_config: Dict[str, Any]) -> Dict[str, Any]:
        """Import a config entry from configuration.yaml."""
        # Check if new config entry matches any existing config entries
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if _host_is_same(entry.data[CONF_HOST], import_config[CONF_HOST]):
                updated_options = {}
                updated_name = {}

                if entry.data[CONF_NAME] != import_config[CONF_NAME]:
                    updated_name[CONF_NAME] = import_config[CONF_NAME]

                if entry.data.get(CONF_VOLUME_STEP) != import_config[CONF_VOLUME_STEP]:
                    updated_options[CONF_VOLUME_STEP] = import_config[CONF_VOLUME_STEP]

                if updated_options or updated_name:
                    new_data = entry.data.copy()
                    new_options = entry.options.copy()

                    if updated_name:
                        new_data.update(updated_name)

                    if updated_options:
                        new_data.update(updated_options)
                        new_options.update(updated_options)

                    self.hass.config_entries.async_update_entry(
                        entry=entry, data=new_data, options=new_options,
                    )
                    return self.async_abort(reason="updated_entry")

                return self.async_abort(reason="already_setup")

        return await self.async_step_user(user_input=import_config)

    async def async_step_zeroconf(
        self, discovery_info: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle zeroconf discovery."""

        # Set unique ID early to prevent device from getting rediscovered multiple times
        await self.async_set_unique_id(
            unique_id=discovery_info[CONF_HOST].split(":")[0], raise_on_progress=True
        )

        discovery_info[
            CONF_HOST
        ] = f"{discovery_info[CONF_HOST]}:{discovery_info[CONF_PORT]}"

        # Check if new config entry matches any existing config entries and abort if so
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if _host_is_same(entry.data[CONF_HOST], discovery_info[CONF_HOST]):
                return self.async_abort(reason="already_setup")

        # Set default name to discovered device name by stripping zeroconf service
        # (`type`) from `name`
        num_chars_to_strip = len(discovery_info[CONF_TYPE]) + 1
        discovery_info[CONF_NAME] = discovery_info[CONF_NAME][:-num_chars_to_strip]

        discovery_info[CONF_DEVICE_CLASS] = await async_guess_device_type(
            discovery_info[CONF_HOST]
        )

        # Form must be shown after discovery so user can confirm/update configuration before ConfigEntry creation.
        self._must_show_form = True

        return await self.async_step_user(user_input=discovery_info)
