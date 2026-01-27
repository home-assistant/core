"""Config flow for victron mqtt integration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
from typing import Any
from urllib.parse import urlparse

from victron_mqtt import (
    AuthenticationError,
    CannotConnectError,
    DeviceType,
    Hub as VictronVenusHub,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers.selector import SelectOptionDict
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    CONF_UPDATE_FREQUENCY_SECONDS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_UPDATE_FREQUENCY_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_CODES: Sequence[SelectOptionDict] = [
    {"value": device_type.code, "label": device_type.string}
    for device_type in DeviceType
    if device_type.string != "<Not used>"
]

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_SSL, default=False): bool,
        vol.Optional(CONF_ROOT_TOPIC_PREFIX): str,
        vol.Optional(
            CONF_UPDATE_FREQUENCY_SECONDS, default=DEFAULT_UPDATE_FREQUENCY_SECONDS
        ): int,
    }
)


async def validate_input(data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from zeroconf values as well as user input.

    Returns the installation id upon success.
    """
    _LOGGER.info("Validating input: %s", data)
    hub = VictronVenusHub(
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        username=data.get(CONF_USERNAME) or None,
        password=data.get(CONF_PASSWORD) or None,
        use_ssl=data.get(CONF_SSL, False),
        installation_id=data.get(CONF_INSTALLATION_ID) or None,
        serial=data.get(CONF_SERIAL, "noserial"),
        topic_prefix=data.get(CONF_ROOT_TOPIC_PREFIX) or None,
    )

    await hub.connect()
    assert hub.installation_id is not None
    return hub.installation_id


class VictronMQTTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for victronvenus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.hostname: str | None = None
        self.serial: str | None = None
        self.installation_id: str | None = None
        self.friendly_name: str | None = None
        self.model_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.info("User input received: %s", user_input)
            data = {**user_input, CONF_SERIAL: self.serial, CONF_MODEL: self.model_name}
            data = {
                k: v for k, v in data.items() if v is not None
            }  # remove None values.

            try:
                installation_id = await validate_input(data)
                _LOGGER.info(
                    "Successfully connected to Victron device: %s", installation_id
                )
            except AuthenticationError:
                _LOGGER.exception("Authentication failed during reauthentication")
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                _LOGGER.exception("Cannot connect to Victron device")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("General error connecting to Victron device")
                errors["base"] = "unknown"
            else:
                data[CONF_INSTALLATION_ID] = installation_id
                unique_id = installation_id
                await self.async_set_unique_id(unique_id)

                self._abort_if_unique_id_configured()

                title = self.friendly_name or f"Victron OS {unique_id}"
                return self.async_create_entry(title=title, data=data)

        if len(errors) > 0:
            _LOGGER.warning("Showing form with errors: %s", errors)
        else:
            _LOGGER.info("Showing form without errors")
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            _LOGGER.info("Reauth user input received: %s", user_input)
            data = {
                **reauth_entry.data,
                CONF_USERNAME: user_input.get(CONF_USERNAME) or None,
                CONF_PASSWORD: user_input.get(CONF_PASSWORD) or None,
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}

            try:
                await validate_input(data)
                _LOGGER.info("Reauthentication successful")
            except AuthenticationError:
                _LOGGER.exception("Authentication failed during reauthentication")
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                _LOGGER.exception("Cannot connect during reauthentication")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("General error during reauthentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        reauth_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USERNAME, default=reauth_entry.data.get(CONF_USERNAME) or ""
                ): str,
                vol.Optional(
                    CONF_PASSWORD, default=reauth_entry.data.get(CONF_PASSWORD) or ""
                ): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema,
            errors=errors,
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> VictronMQTTOptionsFlow:
        """Get the options flow for this handler."""
        _LOGGER.info("Getting options flow handler")
        return VictronMQTTOptionsFlow()

    async def async_step_ssdp_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle SSDP auth when credentials are required."""
        assert self.hostname is not None
        assert self.installation_id is not None

        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.info("SSDP auth user input received: %s", user_input)
            data: dict[str, Any] = {
                CONF_HOST: self.hostname,
                CONF_SERIAL: self.serial,
                CONF_INSTALLATION_ID: self.installation_id,
                CONF_USERNAME: user_input.get(CONF_USERNAME) or None,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}

            try:
                await validate_input(data)
                _LOGGER.info("SSDP authentication successful")
            except AuthenticationError:
                _LOGGER.exception("Authentication failed during SSDP setup")
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                _LOGGER.exception("Cannot connect during SSDP setup")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("General error during SSDP setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{self.model_name} ({self.serial})",
                    data=data,
                )

        auth_schema = vol.Schema(
            {
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="ssdp_auth",
            data_schema=auth_schema,
            errors=errors,
            description_placeholders={"host": self.hostname},
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle UPnP  discovery."""
        self.hostname = str(urlparse(discovery_info.ssdp_location).hostname)
        self.serial = discovery_info.upnp["serialNumber"]
        self.installation_id = discovery_info.upnp["X_VrmPortalId"]
        self.model_name = discovery_info.upnp["modelName"]
        self.friendly_name = discovery_info.upnp["friendlyName"]
        _LOGGER.debug(
            "SSDP: hostname=%s, serial=%s, installation_id=%s, model_name=%s, friendly_name=%s",
            self.hostname,
            self.serial,
            self.installation_id,
            self.model_name,
            self.friendly_name,
        )

        await self.async_set_unique_id(self.installation_id)
        self._abort_if_unique_id_configured()

        try:
            ssdp_conf = {
                CONF_HOST: self.hostname,
                CONF_SERIAL: self.serial,
                CONF_INSTALLATION_ID: self.installation_id,
            }
            sensed_installation_id = await validate_input(ssdp_conf)
            assert sensed_installation_id == self.installation_id
        except AuthenticationError:
            return await self.async_step_ssdp_auth()
        except CannotConnectError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=str(self.friendly_name),
            data={
                CONF_HOST: self.hostname,
                CONF_SERIAL: self.serial,
                CONF_INSTALLATION_ID: self.installation_id,
                CONF_MODEL: self.model_name,
            },
        )


class VictronMQTTOptionsFlow(OptionsFlow):
    """Handle options flow for Victron MQTT."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        _LOGGER.info(
            "Initializing options flow. current config: %s", self.config_entry.data
        )
        if user_input is not None:
            _LOGGER.info("User input received: %s", user_input)
            try:
                await validate_input(user_input)
            except AuthenticationError:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._get_options_schema(),
                    errors={"base": "invalid_auth"},
                )
            except CannotConnectError:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._get_options_schema(),
                    errors={"base": "cannot_connect"},
                )
            _LOGGER.info(
                "Options flow completed successfully. new config: %s", user_input
            )
            # Update the config entry with new data.
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input
            )
            # Reload the entry to apply the new options
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="init",
            data_schema=self._get_options_schema(),
        )

    def _get_options_schema(self) -> vol.Schema:
        """Get the options schema with current values as defaults."""
        return self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, self.config_entry.data
        )
