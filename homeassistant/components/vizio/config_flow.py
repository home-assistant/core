"""Config flow for Vizio."""
import copy
import logging
from typing import Any, Dict, Optional

from pyvizio import VizioAsync, async_guess_device_type
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DEVICE_CLASS_SPEAKER, DEVICE_CLASS_TV
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_IMPORT,
    SOURCE_ZEROCONF,
    ConfigEntry,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_NAME,
    CONF_PIN,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (
    CONF_APPS,
    CONF_APPS_TO_INCLUDE_OR_EXCLUDE,
    CONF_INCLUDE_OR_EXCLUDE,
    CONF_VOLUME_STEP,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DEVICE_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _get_config_schema(input_dict: Dict[str, Any] = None) -> vol.Schema:
    """
    Return schema defaults for init step based on user input/config dict.

    Retain info already provided for future form views by setting them
    as defaults in schema.
    """
    if input_dict is None:
        input_dict = {}

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=input_dict.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            vol.Required(CONF_HOST, default=input_dict.get(CONF_HOST)): str,
            vol.Required(
                CONF_DEVICE_CLASS,
                default=input_dict.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
            ): vol.All(str, vol.Lower, vol.In([DEVICE_CLASS_TV, DEVICE_CLASS_SPEAKER])),
            vol.Optional(
                CONF_ACCESS_TOKEN, default=input_dict.get(CONF_ACCESS_TOKEN, "")
            ): str,
        },
        extra=vol.REMOVE_EXTRA,
    )


def _get_pairing_schema(input_dict: Dict[str, Any] = None) -> vol.Schema:
    """
    Return schema defaults for pairing data based on user input.

    Retain info already provided for future form views by setting
    them as defaults in schema.
    """
    if input_dict is None:
        input_dict = {}

    return vol.Schema(
        {vol.Required(CONF_PIN, default=input_dict.get(CONF_PIN, "")): str}
    )


def _host_is_same(host1: str, host2: str) -> bool:
    """Check if host1 and host2 are the same."""
    return host1.split(":")[0] == host2.split(":")[0]


class VizioOptionsConfigFlow(config_entries.OptionsFlow):
    """Handle Vizio options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize vizio options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Manage the vizio options."""
        if user_input is not None:
            if user_input.get(CONF_APPS_TO_INCLUDE_OR_EXCLUDE):
                user_input[CONF_APPS] = {
                    user_input[CONF_INCLUDE_OR_EXCLUDE]: user_input[
                        CONF_APPS_TO_INCLUDE_OR_EXCLUDE
                    ].copy()
                }

                user_input.pop(CONF_INCLUDE_OR_EXCLUDE)
                user_input.pop(CONF_APPS_TO_INCLUDE_OR_EXCLUDE)

            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_VOLUME_STEP,
                default=self.config_entry.options.get(
                    CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10))
        }

        if self.config_entry.data[CONF_DEVICE_CLASS] == DEVICE_CLASS_TV:
            default_include_or_exclude = (
                CONF_EXCLUDE
                if self.config_entry.options
                and CONF_EXCLUDE in self.config_entry.options.get(CONF_APPS, {})
                else CONF_INCLUDE
            )
            options.update(
                {
                    vol.Optional(
                        CONF_INCLUDE_OR_EXCLUDE,
                        default=default_include_or_exclude.title(),
                    ): vol.All(
                        vol.In([CONF_INCLUDE.title(), CONF_EXCLUDE.title()]), vol.Lower
                    ),
                    vol.Optional(
                        CONF_APPS_TO_INCLUDE_OR_EXCLUDE,
                        default=self.config_entry.options.get(CONF_APPS, {}).get(
                            default_include_or_exclude, []
                        ),
                    ): cv.multi_select(VizioAsync.get_apps_list()),
                }
            )

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
        self._ch_type = None
        self._pairing_token = None
        self._data = None
        self._apps = {}

    async def _create_entry_if_unique(
        self, input_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create entry if ID is unique.

        If it is, create entry. If it isn't, abort config flow.
        """
        # Remove extra keys that will not be used by entry setup
        input_dict.pop(CONF_APPS_TO_INCLUDE_OR_EXCLUDE, None)
        input_dict.pop(CONF_INCLUDE_OR_EXCLUDE, None)

        if self._apps:
            input_dict[CONF_APPS] = self._apps

        return self.async_create_entry(title=input_dict[CONF_NAME], data=input_dict)

    async def async_step_user(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            # Store current values in case setup fails and user needs to edit
            self._user_schema = _get_config_schema(user_input)

            # Check if new config entry matches any existing config entries
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                # If source is ignore bypass host and name check and continue through loop
                if entry.source == SOURCE_IGNORE:
                    continue

                if _host_is_same(entry.data[CONF_HOST], user_input[CONF_HOST]):
                    errors[CONF_HOST] = "host_exists"

                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"

            if not errors:
                # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
                if self._must_show_form and self.context["source"] == SOURCE_ZEROCONF:
                    # Discovery should always display the config form before trying to
                    # create entry so that user can update default config options
                    self._must_show_form = False
                elif user_input[
                    CONF_DEVICE_CLASS
                ] == DEVICE_CLASS_SPEAKER or user_input.get(CONF_ACCESS_TOKEN):
                    # Ensure config is valid for a device
                    if not await VizioAsync.validate_ha_config(
                        user_input[CONF_HOST],
                        user_input.get(CONF_ACCESS_TOKEN),
                        user_input[CONF_DEVICE_CLASS],
                        session=async_get_clientsession(self.hass, False),
                    ):
                        errors["base"] = "cant_connect"

                    if not errors:
                        unique_id = await VizioAsync.get_unique_id(
                            user_input[CONF_HOST],
                            user_input.get(CONF_ACCESS_TOKEN),
                            user_input[CONF_DEVICE_CLASS],
                            session=async_get_clientsession(self.hass, False),
                        )

                        # Set unique ID and abort if unique ID is already configured on an entry or a flow
                        # with the unique ID is already in progress
                        await self.async_set_unique_id(
                            unique_id=unique_id, raise_on_progress=True
                        )
                        self._abort_if_unique_id_configured()

                        return await self._create_entry_if_unique(user_input)
                # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
                elif self._must_show_form and self.context["source"] == SOURCE_IMPORT:
                    # Import should always display the config form if CONF_ACCESS_TOKEN
                    # wasn't included but is needed so that the user can choose to update
                    # their configuration.yaml or to proceed with config flow pairing. We
                    # will also provide contextual message to user explaining why
                    _LOGGER.warning(
                        "Couldn't complete configuration.yaml import: '%s' key is "
                        "missing. Either provide '%s' key in configuration.yaml or "
                        "finish setup by completing configuration via frontend.",
                        CONF_ACCESS_TOKEN,
                        CONF_ACCESS_TOKEN,
                    )
                    self._must_show_form = False
                else:
                    self._data = copy.deepcopy(user_input)
                    return await self.async_step_pair_tv()

        schema = self._user_schema or _get_config_schema()

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        if errors and self.context["source"] == SOURCE_IMPORT:
            # Log an error message if import config flow fails since otherwise failure is silent
            _LOGGER.error(
                "configuration.yaml import failure: %s", ", ".join(errors.values())
            )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, import_config: Dict[str, Any]) -> Dict[str, Any]:
        """Import a config entry from configuration.yaml."""
        # Check if new config entry matches any existing config entries
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            # If source is ignore bypass host check and continue through loop
            if entry.source == SOURCE_IGNORE:
                continue

            if _host_is_same(entry.data[CONF_HOST], import_config[CONF_HOST]):
                updated_options = {}
                updated_data = {}
                remove_apps = False

                if entry.data[CONF_NAME] != import_config[CONF_NAME]:
                    updated_data[CONF_NAME] = import_config[CONF_NAME]

                # Update entry.data[CONF_APPS] if import_config[CONF_APPS] differs, and
                # pop entry.data[CONF_APPS] if import_config[CONF_APPS] is not specified
                if entry.data.get(CONF_APPS) != import_config.get(CONF_APPS):
                    if not import_config.get(CONF_APPS):
                        remove_apps = True
                    else:
                        updated_options[CONF_APPS] = import_config[CONF_APPS]

                if entry.data.get(CONF_VOLUME_STEP) != import_config[CONF_VOLUME_STEP]:
                    updated_options[CONF_VOLUME_STEP] = import_config[CONF_VOLUME_STEP]

                if updated_options or updated_data or remove_apps:
                    new_data = entry.data.copy()
                    new_options = entry.options.copy()

                    if remove_apps:
                        new_data.pop(CONF_APPS)
                        new_options.pop(CONF_APPS)

                    if updated_data:
                        new_data.update(updated_data)

                    if updated_options:
                        new_data.update(updated_options)
                        new_options.update(updated_options)

                    self.hass.config_entries.async_update_entry(
                        entry=entry, data=new_data, options=new_options
                    )
                    return self.async_abort(reason="updated_entry")

                return self.async_abort(reason="already_setup")

        self._must_show_form = True
        # Store config key/value pairs that are not configurable in user step so they
        # don't get lost on user step
        if import_config.get(CONF_APPS):
            self._apps = copy.deepcopy(import_config[CONF_APPS])
        return await self.async_step_user(user_input=import_config)

    async def async_step_zeroconf(
        self, discovery_info: Optional[DiscoveryInfoType] = None
    ) -> Dict[str, Any]:
        """Handle zeroconf discovery."""

        # Set unique ID early to prevent device from getting rediscovered multiple times
        await self.async_set_unique_id(
            unique_id=discovery_info[CONF_HOST].split(":")[0], raise_on_progress=True
        )
        self._abort_if_unique_id_configured()

        discovery_info[
            CONF_HOST
        ] = f"{discovery_info[CONF_HOST]}:{discovery_info[CONF_PORT]}"

        # Check if new config entry matches any existing config entries and abort if so
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            # If source is ignore bypass host check and continue through loop
            if entry.source == SOURCE_IGNORE:
                continue

            if _host_is_same(entry.data[CONF_HOST], discovery_info[CONF_HOST]):
                return self.async_abort(reason="already_setup")

        # Set default name to discovered device name by stripping zeroconf service
        # (`type`) from `name`
        num_chars_to_strip = len(discovery_info[CONF_TYPE]) + 1
        discovery_info[CONF_NAME] = discovery_info[CONF_NAME][:-num_chars_to_strip]

        discovery_info[CONF_DEVICE_CLASS] = await async_guess_device_type(
            discovery_info[CONF_HOST]
        )

        # Form must be shown after discovery so user can confirm/update configuration
        # before ConfigEntry creation.
        self._must_show_form = True
        return await self.async_step_user(user_input=discovery_info)

    async def async_step_pair_tv(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Start pairing process for TV.

        Ask user for PIN to complete pairing process.
        """
        errors = {}

        # Start pairing process if it hasn't already started
        if not self._ch_type and not self._pairing_token:
            dev = VizioAsync(
                DEVICE_ID,
                self._data[CONF_HOST],
                self._data[CONF_NAME],
                None,
                self._data[CONF_DEVICE_CLASS],
                session=async_get_clientsession(self.hass, False),
            )
            pair_data = await dev.start_pair()

            if pair_data:
                self._ch_type = pair_data.ch_type
                self._pairing_token = pair_data.token
                return await self.async_step_pair_tv()

            return self.async_show_form(
                step_id="user",
                data_schema=_get_config_schema(self._data),
                errors={"base": "cant_connect"},
            )

        # Complete pairing process if PIN has been provided
        if user_input and user_input.get(CONF_PIN):
            dev = VizioAsync(
                DEVICE_ID,
                self._data[CONF_HOST],
                self._data[CONF_NAME],
                None,
                self._data[CONF_DEVICE_CLASS],
                session=async_get_clientsession(self.hass, False),
            )
            pair_data = await dev.pair(
                self._ch_type, self._pairing_token, user_input[CONF_PIN]
            )

            if pair_data:
                self._data[CONF_ACCESS_TOKEN] = pair_data.auth_token
                self._must_show_form = True

                unique_id = await VizioAsync.get_unique_id(
                    self._data[CONF_HOST],
                    self._data[CONF_ACCESS_TOKEN],
                    self._data[CONF_DEVICE_CLASS],
                    session=async_get_clientsession(self.hass, False),
                )

                # Set unique ID and abort if unique ID is already configured on an entry or a flow
                # with the unique ID is already in progress
                await self.async_set_unique_id(
                    unique_id=unique_id, raise_on_progress=True
                )
                self._abort_if_unique_id_configured()

                # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
                if self.context["source"] == SOURCE_IMPORT:
                    # If user is pairing via config import, show different message
                    return await self.async_step_pairing_complete_import()

                return await self.async_step_pairing_complete()

            # If no data was retrieved, it's assumed that the pairing attempt was not
            # successful
            errors[CONF_PIN] = "complete_pairing_failed"

        return self.async_show_form(
            step_id="pair_tv",
            data_schema=_get_pairing_schema(user_input),
            errors=errors,
        )

    async def _pairing_complete(self, step_id: str) -> Dict[str, Any]:
        """Handle config flow completion."""
        if not self._must_show_form:
            return await self._create_entry_if_unique(self._data)

        self._must_show_form = False
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({}),
            description_placeholders={"access_token": self._data[CONF_ACCESS_TOKEN]},
        )

    async def async_step_pairing_complete(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Complete non-import sourced config flow.

        Display final message to user confirming pairing.
        """
        return await self._pairing_complete("pairing_complete")

    async def async_step_pairing_complete_import(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Complete import sourced config flow.

        Display final message to user confirming pairing and displaying
        access token.
        """
        return await self._pairing_complete("pairing_complete_import")
