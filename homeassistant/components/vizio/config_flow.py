"""Config flow for Vizio."""

from collections.abc import Mapping
import copy
import logging
import socket
from typing import Any, override

from vizaio import AppRecord, PairChallenge, Vizio, VizioError, async_is_tv
from vizaio.apps import APP_HOME, BUNDLED_APPS
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_ZEROCONF,
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util.network import is_ip_address

from . import DATA_APPS
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
    VIZIO_DEVICE_CLASSES,
)
from .coordinator import VizioConfigEntry

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
            # Name field is no longer allowed in config flow schemas
            # pylint: disable-next=home-assistant-config-flow-name-field
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
    host1 = host1.split(":", maxsplit=1)[0]
    host1 = host1 if is_ip_address(host1) else socket.gethostbyname(host1)
    host2 = host2.split(":", maxsplit=1)[0]
    host2 = host2 if is_ip_address(host2) else socket.gethostbyname(host2)
    return host1 == host2


def _get_device(
    hass: HomeAssistant,
    host: str,
    device_class: str,
    auth_token: str | None = None,
) -> Vizio:
    """Build a client for config flow validation calls."""
    return Vizio(
        host,
        device_type=VIZIO_DEVICE_CLASSES[MediaPlayerDeviceClass(device_class)],
        auth_token=auth_token,
        session=async_get_clientsession(hass, False),
    )


async def _async_get_unique_id(
    hass: HomeAssistant, host: str, device_class: str
) -> str | None:
    """Return the device serial number, or None if unavailable."""
    try:
        return await _get_device(hass, host, device_class).get_serial_number()
    except VizioError:
        return None


async def _async_validate_config(
    hass: HomeAssistant, host: str, auth_token: str | None, device_class: str
) -> bool:
    """Return whether the device is reachable (and the token valid, if any)."""
    device = _get_device(hass, host, device_class, auth_token)
    try:
        if auth_token:
            await device.ping_auth()
        else:
            await device.ping()
    except VizioError:
        return False
    return True


class VizioOptionsConfigFlow(OptionsFlow):
    """Handle Vizio options."""

    def _get_app_list(self) -> tuple[AppRecord, ...]:
        """Return the current apps list, falling back to defaults."""
        if (
            apps_coordinator := self.hass.data.get(DATA_APPS)
        ) and apps_coordinator.data:
            return apps_coordinator.data
        return BUNDLED_APPS

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
                            APP_HOME.name,
                            *(app.name for app in self._get_app_list()),
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
    @override
    def async_get_options_flow(
        config_entry: VizioConfigEntry,
    ) -> VizioOptionsConfigFlow:
        """Get the options flow for this handler."""
        return VizioOptionsConfigFlow()

    def __init__(self) -> None:
        """Initialize config flow."""
        self._user_schema: vol.Schema | None = None
        self._must_show_form: bool | None = None
        self._pair_challenge: PairChallenge | None = None
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

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store current values in case setup fails and user needs to edit
            self._user_schema = _get_config_schema(user_input)
            if self.unique_id is None:
                unique_id = await _async_get_unique_id(
                    self.hass, user_input[CONF_HOST], user_input[CONF_DEVICE_CLASS]
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
                    if not await _async_validate_config(
                        self.hass,
                        user_input[CONF_HOST],
                        user_input.get(CONF_ACCESS_TOKEN),
                        user_input[CONF_DEVICE_CLASS],
                    ):
                        errors["base"] = "cannot_connect"

                    if not errors:
                        return await self._create_entry(user_input)
                else:
                    self._data = copy.deepcopy(user_input)
                    return await self.async_step_pair_tv()

        schema = self._user_schema or _get_config_schema()
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
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

        device_class = (
            MediaPlayerDeviceClass.TV
            if await async_is_tv(host)
            else MediaPlayerDeviceClass.SPEAKER
        )

        # Set unique ID early for discovery flow so we can abort if needed
        unique_id = await _async_get_unique_id(self.hass, host, device_class)

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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization when the stored access token is rejected."""
        self._data = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth; continuing puts a pairing PIN on the TV screen."""
        if user_input is not None:
            return await self.async_step_pair_tv()
        return self.async_show_form(step_id="reauth_confirm")

    async def async_step_pair_tv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start pairing process for TV.

        Ask user for PIN to complete pairing process.
        """
        errors: dict[str, str] = {}
        assert self._data

        # Start pairing process if it hasn't already started
        if not self._pair_challenge:
            dev = _get_device(
                self.hass, self._data[CONF_HOST], self._data[CONF_DEVICE_CLASS]
            )
            try:
                self._pair_challenge = await dev.begin_pair(
                    device_id=DEVICE_ID, device_name=self._data[CONF_NAME]
                )
            except VizioError:
                if self.source == SOURCE_REAUTH:
                    return self.async_show_form(
                        step_id="reauth_confirm",
                        errors={"base": "cannot_connect"},
                    )
                return self.async_show_form(
                    step_id="user",
                    data_schema=_get_config_schema(self._data),
                    errors={"base": "cannot_connect"},
                )
            return await self.async_step_pair_tv()

        # Complete pairing process if PIN has been provided
        if user_input and user_input.get(CONF_PIN):
            dev = _get_device(
                self.hass, self._data[CONF_HOST], self._data[CONF_DEVICE_CLASS]
            )
            try:
                auth_token = await dev.finish_pair(
                    device_id=DEVICE_ID,
                    challenge=self._pair_challenge,
                    pin=user_input[CONF_PIN],
                )
            except VizioError:
                # If pairing failed, it's assumed the PIN was invalid
                errors[CONF_PIN] = "complete_pairing_failed"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates={CONF_ACCESS_TOKEN: auth_token},
                    )
                self._data[CONF_ACCESS_TOKEN] = auth_token
                self._must_show_form = True
                return await self.async_step_pairing_complete()

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
