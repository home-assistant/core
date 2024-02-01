"""Config flow for Enphase Envoy integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from awesomeversion import AwesomeVersion
from pyenphase import AUTH_TOKEN_MIN_VERSION, Envoy, EnvoyError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, INVALID_AUTH_ERRORS

_LOGGER = logging.getLogger(__name__)

ENVOY = "Envoy"

CONF_SERIAL = "serial"

INSTALLER_AUTH_USERNAME = "installer"


async def validate_input(
    hass: HomeAssistant, host: str, username: str, password: str
) -> Envoy:
    """Validate the user input allows us to connect."""
    envoy = Envoy(host, get_async_client(hass, verify_ssl=False))
    await envoy.setup()
    await envoy.authenticate(username=username, password=password)
    return envoy


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enphase Envoy."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize an envoy flow."""
        self.ip_address: str | None = None
        self.username = None
        self.protovers: str | None = None
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @callback
    def _async_generate_schema(self) -> vol.Schema:
        """Generate schema."""
        schema = {}

        if self.ip_address:
            schema[vol.Required(CONF_HOST, default=self.ip_address)] = vol.In(
                [self.ip_address]
            )
        elif not self._reauth_entry:
            schema[vol.Required(CONF_HOST)] = str

        default_username = ""
        if (
            not self.username
            and self.protovers
            and AwesomeVersion(self.protovers) < AUTH_TOKEN_MIN_VERSION
        ):
            default_username = INSTALLER_AUTH_USERNAME

        schema[
            vol.Optional(CONF_USERNAME, default=self.username or default_username)
        ] = str
        schema[vol.Optional(CONF_PASSWORD, default="")] = str

        return vol.Schema(schema)

    @callback
    def _async_current_hosts(self) -> set[str]:
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        if discovery_info.ip_address.version != 4:
            return self.async_abort(reason="not_ipv4_address")
        serial = discovery_info.properties["serialnum"]
        self.protovers = discovery_info.properties.get("protovers")
        await self.async_set_unique_id(serial)
        self.ip_address = discovery_info.host
        self._abort_if_unique_id_configured({CONF_HOST: self.ip_address})
        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.unique_id is None
                and CONF_HOST in entry.data
                and entry.data[CONF_HOST] == self.ip_address
            ):
                title = f"{ENVOY} {serial}" if entry.title == ENVOY else ENVOY
                return self.async_update_reload_and_abort(
                    entry, title=title, unique_id=serial, reason="already_configured"
                )

        return await self.async_step_user()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        assert self._reauth_entry is not None
        if unique_id := self._reauth_entry.unique_id:
            await self.async_set_unique_id(unique_id, raise_on_progress=False)
        return await self.async_step_user()

    def _async_envoy_name(self) -> str:
        """Return the name of the envoy."""
        return f"{ENVOY} {self.unique_id}" if self.unique_id else ENVOY

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if self._reauth_entry:
            host = self._reauth_entry.data[CONF_HOST]
        else:
            host = (user_input or {}).get(CONF_HOST) or self.ip_address or ""

        if user_input is not None:
            if not self._reauth_entry:
                if host in self._async_current_hosts():
                    return self.async_abort(reason="already_configured")

            try:
                envoy = await validate_input(
                    self.hass,
                    host,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except INVALID_AUTH_ERRORS as e:
                errors["base"] = "invalid_auth"
                description_placeholders = {"reason": str(e)}
            except EnvoyError as e:
                errors["base"] = "cannot_connect"
                description_placeholders = {"reason": str(e)}
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                name = self._async_envoy_name()

                if self._reauth_entry:
                    return self.async_update_reload_and_abort(
                        self._reauth_entry,
                        data=self._reauth_entry.data | user_input,
                    )

                if not self.unique_id:
                    await self.async_set_unique_id(envoy.serial_number)
                    name = self._async_envoy_name()

                if self.unique_id:
                    self._abort_if_unique_id_configured({CONF_HOST: host})

                # CONF_NAME is still set for legacy backwards compatibility
                return self.async_create_entry(
                    title=name, data={CONF_HOST: host, CONF_NAME: name} | user_input
                )

        if self.unique_id:
            self.context["title_placeholders"] = {
                CONF_SERIAL: self.unique_id,
                CONF_HOST: host,
            }

        return self.async_show_form(
            step_id="user",
            data_schema=self._async_generate_schema(),
            description_placeholders=description_placeholders,
            errors=errors,
        )
