"""Config flow for the Huawei LTE platform."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from huawei_lte_api.AuthorizedConnection import AuthorizedConnection
from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import GetResponseType
from huawei_lte_api.exceptions import (
    LoginErrorPasswordWrongException,
    LoginErrorUsernamePasswordOverrunException,
    LoginErrorUsernamePasswordWrongException,
    LoginErrorUsernameWrongException,
    ResponseErrorException,
)
from requests.exceptions import Timeout
from url_normalize import url_normalize
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (
    CONF_TRACK_WIRED_CLIENTS,
    CONF_UNAUTHENTICATED_MODE,
    CONNECTION_TIMEOUT,
    DEFAULT_DEVICE_NAME,
    DEFAULT_NOTIFY_SERVICE_NAME,
    DEFAULT_TRACK_WIRED_CLIENTS,
    DEFAULT_UNAUTHENTICATED_MODE,
    DOMAIN,
)
from .utils import get_device_macs

_LOGGER = logging.getLogger(__name__)


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Huawei LTE config flow."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get options flow."""
        return OptionsFlowHandler(config_entry)

    async def _async_show_user_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> FlowResult:
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL,
                        default=user_input.get(
                            CONF_URL,
                            self.context.get(CONF_URL, ""),
                        ),
                    ): str,
                    vol.Optional(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME) or ""
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD) or ""
                    ): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle import initiated config flow."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user initiated config flow."""
        if user_input is None:
            return await self._async_show_user_form()

        errors = {}

        # Normalize URL
        user_input[CONF_URL] = url_normalize(
            user_input[CONF_URL], default_scheme="http"
        )
        if "://" not in user_input[CONF_URL]:
            errors[CONF_URL] = "invalid_url"
            return await self._async_show_user_form(
                user_input=user_input, errors=errors
            )

        conn: AuthorizedConnection

        def logout() -> None:
            try:
                conn.user.logout()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Could not logout", exc_info=True)

        def try_connect(user_input: dict[str, Any]) -> AuthorizedConnection:
            """Try connecting with given credentials."""
            username = user_input.get(CONF_USERNAME) or ""
            password = user_input.get(CONF_PASSWORD) or ""
            conn = AuthorizedConnection(
                user_input[CONF_URL],
                username=username,
                password=password,
                timeout=CONNECTION_TIMEOUT,
            )
            return conn

        def get_device_info() -> tuple[GetResponseType, GetResponseType]:
            """Get router info."""
            client = Client(conn)
            try:
                device_info = client.device.information()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Could not get device.information", exc_info=True)
                try:
                    device_info = client.device.basic_information()
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.debug(
                        "Could not get device.basic_information", exc_info=True
                    )
                    device_info = {}
            try:
                wlan_settings = client.wlan.multi_basic_settings()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Could not get wlan.multi_basic_settings", exc_info=True)
                wlan_settings = {}
            return device_info, wlan_settings

        try:
            conn = await self.hass.async_add_executor_job(try_connect, user_input)
        except LoginErrorUsernameWrongException:
            errors[CONF_USERNAME] = "incorrect_username"
        except LoginErrorPasswordWrongException:
            errors[CONF_PASSWORD] = "incorrect_password"
        except LoginErrorUsernamePasswordWrongException:
            errors[CONF_USERNAME] = "invalid_auth"
        except LoginErrorUsernamePasswordOverrunException:
            errors["base"] = "login_attempts_exceeded"
        except ResponseErrorException:
            _LOGGER.warning("Response error", exc_info=True)
            errors["base"] = "response_error"
        except Timeout:
            _LOGGER.warning("Connection timeout", exc_info=True)
            errors[CONF_URL] = "connection_timeout"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.warning("Unknown error connecting to device", exc_info=True)
            errors[CONF_URL] = "unknown"
        if errors:
            await self.hass.async_add_executor_job(logout)
            return await self._async_show_user_form(
                user_input=user_input, errors=errors
            )

        info, wlan_settings = await self.hass.async_add_executor_job(get_device_info)
        await self.hass.async_add_executor_job(logout)

        if not self.unique_id:
            if serial_number := info.get("SerialNumber"):
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()
            else:
                await self._async_handle_discovery_without_unique_id()

        user_input[CONF_MAC] = get_device_macs(info, wlan_settings)

        title = (
            self.context.get("title_placeholders", {}).get(CONF_NAME)
            or info.get("DeviceName")  # device.information
            or info.get("devicename")  # device.basic_information
            or DEFAULT_DEVICE_NAME
        )

        return self.async_create_entry(title=title, data=user_input)

    async def async_step_ssdp(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        """Handle SSDP initiated config flow."""
        await self.async_set_unique_id(discovery_info[ssdp.ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured()

        # Attempt to distinguish from other non-LTE Huawei router devices, at least
        # some ones we are interested in have "Mobile Wi-Fi" friendlyName.
        if "mobile" not in discovery_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME, "").lower():
            return self.async_abort(reason="not_huawei_lte")

        url = url_normalize(
            discovery_info.get(
                ssdp.ATTR_UPNP_PRESENTATION_URL,
                f"http://{urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname}/",
            )
        )

        if serial_number := discovery_info.get(ssdp.ATTR_UPNP_SERIAL):
            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured()
        else:
            await self._async_handle_discovery_without_unique_id()

        user_input = {CONF_URL: url}

        self.context["title_placeholders"] = {
            CONF_NAME: discovery_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
        }
        return await self._async_show_user_form(user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Huawei LTE options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""

        # Recipients are persisted as a list, but handled as comma separated string in UI

        if user_input is not None:
            # Preserve existing options, for example *_from_yaml markers
            data = {**self.config_entry.options, **user_input}
            if not isinstance(data[CONF_RECIPIENT], list):
                data[CONF_RECIPIENT] = [
                    x.strip() for x in data[CONF_RECIPIENT].split(",")
                ]
            return self.async_create_entry(title="", data=data)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NAME,
                    default=self.config_entry.options.get(
                        CONF_NAME, DEFAULT_NOTIFY_SERVICE_NAME
                    ),
                ): str,
                vol.Optional(
                    CONF_RECIPIENT,
                    default=", ".join(
                        self.config_entry.options.get(CONF_RECIPIENT, [])
                    ),
                ): str,
                vol.Optional(
                    CONF_TRACK_WIRED_CLIENTS,
                    default=self.config_entry.options.get(
                        CONF_TRACK_WIRED_CLIENTS, DEFAULT_TRACK_WIRED_CLIENTS
                    ),
                ): bool,
                vol.Optional(
                    CONF_UNAUTHENTICATED_MODE,
                    default=self.config_entry.options.get(
                        CONF_UNAUTHENTICATED_MODE, DEFAULT_UNAUTHENTICATED_MODE
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
