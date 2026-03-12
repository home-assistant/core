"""Config flow for victron mqtt integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from victron_mqtt import AuthenticationError, CannotConnectError, Hub as VictronVenusHub
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers.redact import async_redact_data
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    DOMAIN,
)

DEFAULT_HOST = "venus.local"
DEFAULT_PORT = 1883

_LOGGER = logging.getLogger(__name__)

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}

ENTRY_TITLE_FORMAT = "Victron OS {installation_id} ({host}:{port})"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_SSL, default=False): bool,
        vol.Optional(CONF_ROOT_TOPIC_PREFIX): str,
    }
)


async def validate_input(data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from SSDP values as well as user input.

    Returns the installation id upon success.
    """
    _LOGGER.debug("Validating input: %s", async_redact_data(data, TO_REDACT))
    hub: VictronVenusHub | None = None
    try:
        hub = VictronVenusHub(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
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
    finally:
        if hub is not None:
            try:
                await hub.disconnect()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Ignoring disconnect error during config validation")


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
            _LOGGER.debug(
                "User input received: %s",
                async_redact_data(user_input, TO_REDACT),
            )
            data = {**user_input, CONF_SERIAL: self.serial, CONF_MODEL: self.model_name}

            try:
                installation_id = await validate_input(data)
                _LOGGER.debug(
                    "Successfully connected to Victron device: %s", installation_id
                )
            except AuthenticationError:
                _LOGGER.debug(
                    "Authentication failed during initial setup", exc_info=True
                )
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                _LOGGER.debug("Cannot connect to Victron device", exc_info=True)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to Victron device")
                errors["base"] = "unknown"
            else:
                data[CONF_INSTALLATION_ID] = installation_id
                unique_id = installation_id
                await self.async_set_unique_id(unique_id)

                self._abort_if_unique_id_configured()
                title = ENTRY_TITLE_FORMAT.format(
                    installation_id=installation_id,
                    host=data[CONF_HOST],
                    port=data.get(CONF_PORT, DEFAULT_PORT),
                )
                return self.async_create_entry(title=title, data=data)

        _LOGGER.debug("Showing form with errors: %s", errors)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery."""
        self.hostname = str(urlparse(discovery_info.ssdp_location).hostname)
        self.serial = discovery_info.upnp["serialNumber"]
        self.installation_id = discovery_info.upnp["X_VrmPortalId"]
        self.model_name = discovery_info.upnp["modelName"]
        self.friendly_name = discovery_info.upnp["friendlyName"]

        await self.async_set_unique_id(self.installation_id)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": self.friendly_name}
        return await self.async_step_ssdp_confirm()

    async def async_step_ssdp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm SSDP discovered device."""
        assert self.hostname is not None
        assert self.installation_id is not None

        if user_input is not None:
            try:
                ssdp_conf = {
                    CONF_HOST: self.hostname,
                    CONF_PORT: DEFAULT_PORT,
                    CONF_SERIAL: self.serial,
                    CONF_INSTALLATION_ID: self.installation_id,
                }
                await validate_input(ssdp_conf)
            except AuthenticationError:
                return await self.async_step_ssdp_auth()
            except CannotConnectError:
                return self.async_abort(reason="cannot_connect")

            return self.async_create_entry(
                title=ENTRY_TITLE_FORMAT.format(
                    installation_id=self.installation_id,
                    host=self.hostname,
                    port=DEFAULT_PORT,
                ),
                data={
                    CONF_HOST: self.hostname,
                    CONF_PORT: DEFAULT_PORT,
                    CONF_SERIAL: self.serial,
                    CONF_INSTALLATION_ID: self.installation_id,
                    CONF_MODEL: self.model_name,
                },
            )

        self._set_confirm_only()
        assert self.friendly_name is not None
        return self.async_show_form(
            step_id="ssdp_confirm",
            description_placeholders={"name": self.friendly_name},
        )

    async def async_step_ssdp_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle SSDP auth when credentials are required."""
        assert self.hostname is not None
        assert self.installation_id is not None

        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug(
                "SSDP auth user input received: %s",
                async_redact_data(user_input, TO_REDACT),
            )
            data: dict[str, Any] = {
                CONF_HOST: self.hostname,
                CONF_PORT: DEFAULT_PORT,
                CONF_SERIAL: self.serial,
                CONF_INSTALLATION_ID: self.installation_id,
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_SSL: user_input.get(CONF_SSL),
            }

            try:
                await validate_input(data)
                _LOGGER.debug("SSDP authentication successful")
            except AuthenticationError:
                _LOGGER.debug("Authentication failed during SSDP setup", exc_info=True)
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                _LOGGER.debug("Cannot connect during SSDP setup", exc_info=True)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during SSDP setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=ENTRY_TITLE_FORMAT.format(
                        installation_id=self.installation_id,
                        host=self.hostname,
                        port=DEFAULT_PORT,
                    ),
                    data=data,
                )

        auth_schema = vol.Schema(
            {
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_SSL, default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="ssdp_auth",
            data_schema=auth_schema,
            errors=errors,
            description_placeholders={"host": self.hostname},
        )
