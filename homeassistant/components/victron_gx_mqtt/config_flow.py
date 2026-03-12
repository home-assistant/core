"""Config flow for victron mqtt integration."""

from __future__ import annotations

from collections.abc import Mapping
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

    Data has the keys from zeroconf values as well as user input.

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

    @staticmethod
    def _build_entry_title(installation_id: str, host: str, port: int) -> str:
        """Build a config entry title."""
        return f"Victron OS {installation_id} ({host}:{port})"

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
            data = {
                k: v for k, v in data.items() if v is not None
            }  # remove None values.

            try:
                installation_id = await validate_input(data)
                _LOGGER.debug(
                    "Successfully connected to Victron device: %s", installation_id
                )
            except AuthenticationError:
                _LOGGER.exception("Authentication failed during initial setup")
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

                title = self._build_entry_title(
                    installation_id,
                    data[CONF_HOST],
                    data.get(CONF_PORT, DEFAULT_PORT),
                )
                return self.async_create_entry(title=title, data=data)

        if len(errors) > 0:
            _LOGGER.warning("Showing form with errors: %s", errors)
        else:
            _LOGGER.debug("Showing form without errors")
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
            _LOGGER.debug(
                "Reauth user input received: %s",
                async_redact_data(user_input, TO_REDACT),
            )
            data = {
                **reauth_entry.data,
                CONF_USERNAME: user_input.get(CONF_USERNAME) or None,
                CONF_PASSWORD: user_input.get(CONF_PASSWORD) or None,
                CONF_SSL: user_input.get(CONF_SSL) or None,
            }
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
                    data=data,
                    reason="reauth_successful",
                )

        reauth_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USERNAME, default=reauth_entry.data.get(CONF_USERNAME, "")
                ): str,
                vol.Optional(
                    CONF_PASSWORD, default=reauth_entry.data.get(CONF_PASSWORD, "")
                ): str,
                vol.Optional(
                    CONF_SSL, default=reauth_entry.data.get(CONF_SSL, False)
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema,
            errors=errors,
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
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
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}

            try:
                await validate_input(data)
                _LOGGER.debug("SSDP authentication successful")
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
                    title=self._build_entry_title(
                        self.installation_id, self.hostname, DEFAULT_PORT
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
                CONF_PORT: DEFAULT_PORT,
                CONF_SERIAL: self.serial,
                CONF_INSTALLATION_ID: self.installation_id,
            }
            sensed_installation_id = await validate_input(ssdp_conf)
            assert sensed_installation_id == self.installation_id
        except AuthenticationError:
            return await self.async_step_ssdp_auth()
        except CannotConnectError:
            return self.async_abort(reason="cannot_connect")

        assert self.installation_id is not None
        return self.async_create_entry(
            title=self._build_entry_title(
                self.installation_id, self.hostname, DEFAULT_PORT
            ),
            data={
                CONF_HOST: self.hostname,
                CONF_PORT: DEFAULT_PORT,
                CONF_SERIAL: self.serial,
                CONF_INSTALLATION_ID: self.installation_id,
                CONF_MODEL: self.model_name,
            },
        )
