"""Config flow for the Reolink camera component."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from reolink_aio.exceptions import ApiError, CredentialsInvalidError, ReolinkError
import voluptuous as vol

from homeassistant.components import dhcp
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
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_USE_HTTPS, DOMAIN
from .exceptions import ReolinkException, ReolinkWebhookException, UserNotAdmin
from .host import ReolinkHost
from .util import is_connected

_LOGGER = logging.getLogger(__name__)

DEFAULT_PROTOCOL = "rtsp"
DEFAULT_OPTIONS = {CONF_PROTOCOL: DEFAULT_PROTOCOL}


class ReolinkOptionsFlowHandler(OptionsFlow):
    """Handle Reolink options."""

    def __init__(self, config_entry):
        """Initialize ReolinkOptionsFlowHandler."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Reolink options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROTOCOL,
                        default=self.config_entry.options[CONF_PROTOCOL],
                    ): vol.In(["rtsp", "rtmp", "flv"]),
                }
            ),
        )


class ReolinkFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reolink device."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host: str | None = None
        self._username: str = "admin"
        self._password: str | None = None
        self._reauth: bool = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ReolinkOptionsFlowHandler:
        """Options callback for Reolink."""
        return ReolinkOptionsFlowHandler(config_entry)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an authentication error or no admin privileges."""
        self._host = entry_data[CONF_HOST]
        self._username = entry_data[CONF_USERNAME]
        self._password = entry_data[CONF_PASSWORD]
        self._reauth = True
        self.context["title_placeholders"]["ip_address"] = entry_data[CONF_HOST]
        self.context["title_placeholders"]["hostname"] = self.context[
            "title_placeholders"
        ]["name"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is not None:
            return await self.async_step_user()
        return self.async_show_form(step_id="reauth_confirm")

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        mac_address = format_mac(discovery_info.macaddress)
        existing_entry = await self.async_set_unique_id(mac_address)
        if (
            existing_entry
            and CONF_PASSWORD in existing_entry.data
            and existing_entry.data[CONF_HOST] != discovery_info.ip
        ):
            if is_connected(self.hass, existing_entry):
                _LOGGER.debug(
                    "Reolink DHCP reported new IP '%s', "
                    "but connection to camera seems to be okay, so sticking to IP '%s'",
                    discovery_info.ip,
                    existing_entry.data[CONF_HOST],
                )
                raise AbortFlow("already_configured")

            # check if the camera is reachable at the new IP
            new_config = dict(existing_entry.data)
            new_config[CONF_HOST] = discovery_info.ip
            host = ReolinkHost(self.hass, new_config, existing_entry.options)
            try:
                await host.api.get_state("GetLocalLink")
                await host.api.logout()
            except ReolinkError as err:
                _LOGGER.debug(
                    "Reolink DHCP reported new IP '%s', "
                    "but got error '%s' trying to connect, so sticking to IP '%s'",
                    discovery_info.ip,
                    err,
                    existing_entry.data[CONF_HOST],
                )
                raise AbortFlow("already_configured") from err
            if format_mac(host.api.mac_address) != mac_address:
                _LOGGER.debug(
                    "Reolink mac address '%s' at new IP '%s' from DHCP, "
                    "does not match mac '%s' of config entry, so sticking to IP '%s'",
                    format_mac(host.api.mac_address),
                    discovery_info.ip,
                    mac_address,
                    existing_entry.data[CONF_HOST],
                )
                raise AbortFlow("already_configured")

        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        self.context["title_placeholders"] = {
            "ip_address": discovery_info.ip,
            "hostname": discovery_info.hostname,
        }

        self._host = discovery_info.ip
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        placeholders = {
            "error": "",
            "troubleshooting_link": "https://www.home-assistant.io/integrations/reolink/#troubleshooting",
        }

        if user_input is not None:
            if CONF_HOST not in user_input:
                user_input[CONF_HOST] = self._host

            host = ReolinkHost(self.hass, user_input, DEFAULT_OPTIONS)
            try:
                await host.async_init()
            except UserNotAdmin:
                errors[CONF_USERNAME] = "not_admin"
                placeholders["username"] = host.api.username
                placeholders["userlevel"] = host.api.user_level
            except CredentialsInvalidError:
                errors[CONF_HOST] = "invalid_auth"
            except ApiError as err:
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "api_error"
            except ReolinkWebhookException as err:
                placeholders["error"] = str(err)
                placeholders["more_info"] = (
                    "https://www.home-assistant.io/more-info/no-url-available/#configuring-the-instance-url"
                )
                errors["base"] = "webhook_exception"
            except (ReolinkError, ReolinkException) as err:
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "unknown"
            finally:
                await host.stop()

            if not errors:
                user_input[CONF_PORT] = host.api.port
                user_input[CONF_USE_HTTPS] = host.api.use_https

                existing_entry = await self.async_set_unique_id(
                    host.unique_id, raise_on_progress=False
                )
                if existing_entry and self._reauth:
                    if self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    ):
                        await self.hass.config_entries.async_reload(
                            existing_entry.entry_id
                        )
                    return self.async_abort(reason="reauth_successful")
                self._abort_if_unique_id_configured(updates=user_input)

                return self.async_create_entry(
                    title=str(host.api.nvr_name),
                    data=user_input,
                    options=DEFAULT_OPTIONS,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=self._username): str,
                vol.Required(CONF_PASSWORD, default=self._password): str,
            }
        )
        if self._host is None or errors:
            data_schema = data_schema.extend(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                }
            )
        if errors:
            data_schema = data_schema.extend(
                {
                    vol.Optional(CONF_PORT): cv.positive_int,
                    vol.Required(CONF_USE_HTTPS, default=False): bool,
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=placeholders,
        )
