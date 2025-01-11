"""Config flow for Vizio."""

from __future__ import annotations

import copy
import logging
import socket
from typing import Any

from pyvizio import VizioAsync, async_guess_device_type
from pyvizio.const import APP_HOME
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.config_entries import (
    SOURCE_ZEROCONF,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_NAME,
    CONF_PIN,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.network import is_ip_address

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


def _get_config_schema(input_dict: dict[str, Any] | None = None) -> vol.Schema:
    """Return schema defaults for init step based on user input/config dict.

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
            ): vol.All(
                str,
                vol.Lower,
                vol.In([MediaPlayerDeviceClass.TV, MediaPlayerDeviceClass.SPEAKER]),
            ),
            vol.Optional(
                CONF_ACCESS_TOKEN, default=input_dict.get(CONF_ACCESS_TOKEN, "")
            ): str,
        },
        extra=vol.REMOVE_EXTRA,
    )


def _get_pairing_schema(input_dict: dict[str, Any] | None = None) -> vol.Schema:
    """Return schema defaults for pairing data based on user input.

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
    host1 = host1.split(":")[0]
    host1 = host1 if is_ip_address(host1) else socket.gethostbyname(host1)
    host2 = host2.split(":")[0]
    host2 = host2 if is_ip_address(host2) else socket.gethostbyname(host2)
    return host1 == host2


class VizioOptionsConfigFlow(OptionsFlow):
    """Handle Vizio options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

        options = vol.Schema(
            {
                vol.Optional(
                    CONF_VOLUME_STEP,
                    default=self.config_entry.options.get(
                        CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10))
            }
        )

        if self.config_entry.data[CONF_DEVICE_CLASS] == MediaPlayerDeviceClass.TV:
            default_include_or_exclude = (
                CONF_EXCLUDE
                if self.config_entry.options
                and CONF_EXCLUDE in self.config_entry.options.get(CONF_APPS, {})
                else CONF_INCLUDE
            )
            options = options.extend(
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
                    ): cv.multi_select(
                        [
                            APP_HOME["name"],
                            *(
                                app["name"]
                                for app in self.hass.data[DOMAIN][CONF_APPS].data
                            ),
                        ]
                    ),
                }
            )

        return self.async_show_form(step_id="init", data_schema=options)


class VizioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Vizio config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> VizioOptionsConfigFlow:
        """Get the options flow for this handler."""
        return VizioOptionsConfigFlow()

    def __init__(self) -> None:
        """Initialize config flow."""
        self._user_schema: vol.Schema | None = None
        self._must_show_form: bool | None = None
        self._ch_type: str | None = None
        self._pairing_token: str | None = None
        self._data: dict[str, Any] | None = None
        self._apps: dict[str, list] = {}

    async def _create_entry(self, input_dict: dict[str, Any]) -> ConfigFlowResult:
        """Create vizio config entry."""
        # Remove extra keys that will not be used by entry setup
        input_dict.pop(CONF_APPS_TO_INCLUDE_OR_EXCLUDE, None)
        input_dict.pop(CONF_INCLUDE_OR_EXCLUDE, None)

        if self._apps:
            input_dict[CONF_APPS] = self._apps

        return self.async_create_entry(title=input_dict[CONF_NAME], data=input_dict)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store current values in case setup fails and user needs to edit
            self._user_schema = _get_config_schema(user_input)
            if self.unique_id is None:
                unique_id = await VizioAsync.get_unique_id(
                    user_input[CONF_HOST],
                    user_input[CONF_DEVICE_CLASS],
                    session=async_get_clientsession(self.hass, False),
                )

                # Check if unique ID was found, set unique ID, and abort if a flow with
                # the same unique ID is already in progress
                if not unique_id:
                    errors[CONF_HOST] = "cannot_connect"
                elif (
                    await self.async_set_unique_id(
                        unique_id=unique_id, raise_on_progress=True
                    )
                    is not None
                ):
                    errors[CONF_HOST] = "existing_config_entry_found"

            if not errors:
                if self._must_show_form and self.context["source"] == SOURCE_ZEROCONF:
                    # Discovery should always display the config form before trying to
                    # create entry so that user can update default config options
                    self._must_show_form = False
                elif user_input[
                    CONF_DEVICE_CLASS
                ] == MediaPlayerDeviceClass.SPEAKER or user_input.get(
                    CONF_ACCESS_TOKEN
                ):
                    # Ensure config is valid for a device
                    if not await VizioAsync.validate_ha_config(
                        user_input[CONF_HOST],
                        user_input.get(CONF_ACCESS_TOKEN),
                        user_input[CONF_DEVICE_CLASS],
                        session=async_get_clientsession(self.hass, False),
                    ):
                        errors["base"] = "cannot_connect"

                    if not errors:
                        return await self._create_entry(user_input)
                else:
                    self._data = copy.deepcopy(user_input)
                    return await self.async_step_pair_tv()

        schema = self._user_schema or _get_config_schema()
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        # If host already has port, no need to add it again
        if ":" not in host:
            host = f"{host}:{discovery_info.port}"

        # Set default name to discovered device name by stripping zeroconf service
        # (`type`) from `name`
        num_chars_to_strip = len(discovery_info.type) + 1
        name = discovery_info.name[:-num_chars_to_strip]

        device_class = await async_guess_device_type(host)

        # Set unique ID early for discovery flow so we can abort if needed
        unique_id = await VizioAsync.get_unique_id(
            host,
            device_class,
            session=async_get_clientsession(self.hass, False),
        )

        if not unique_id:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(unique_id=unique_id, raise_on_progress=True)
        self._abort_if_unique_id_configured()

        # Form must be shown after discovery so user can confirm/update configuration
        # before ConfigEntry creation.
        self._must_show_form = True
        return await self.async_step_user(
            user_input={
                CONF_HOST: host,
                CONF_NAME: name,
                CONF_DEVICE_CLASS: device_class,
            }
        )

    async def async_step_pair_tv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start pairing process for TV.

        Ask user for PIN to complete pairing process.
        """
        errors: dict[str, str] = {}
        assert self._data

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
                errors={"base": "cannot_connect"},
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
                return await self.async_step_pairing_complete()

            # If no data was retrieved, it's assumed that the pairing attempt was not
            # successful
            errors[CONF_PIN] = "complete_pairing_failed"

        return self.async_show_form(
            step_id="pair_tv",
            data_schema=_get_pairing_schema(user_input),
            errors=errors,
        )

    async def _pairing_complete(self, step_id: str) -> ConfigFlowResult:
        """Handle config flow completion."""
        assert self._data
        if not self._must_show_form:
            return await self._create_entry(self._data)

        self._must_show_form = False
        return self.async_show_form(
            step_id=step_id,
            description_placeholders={"access_token": self._data[CONF_ACCESS_TOKEN]},
        )

    async def async_step_pairing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Complete non-import sourced config flow.

        Display final message to user confirming pairing.
        """
        return await self._pairing_complete("pairing_complete")

    async def async_step_pairing_complete_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Complete import sourced config flow.

        Display final message to user confirming pairing and displaying
        access token.
        """
        return await self._pairing_complete("pairing_complete_import")
