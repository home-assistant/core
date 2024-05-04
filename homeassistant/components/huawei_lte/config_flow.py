"""Config flow for the Huawei LTE platform."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection
from huawei_lte_api.exceptions import (
    LoginErrorPasswordWrongException,
    LoginErrorUsernamePasswordOverrunException,
    LoginErrorUsernamePasswordWrongException,
    LoginErrorUsernameWrongException,
    ResponseErrorException,
)
from huawei_lte_api.Session import GetResponseType
from requests.exceptions import SSLError, Timeout
from url_normalize import url_normalize
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback

from .const import (
    CONF_MANUFACTURER,
    CONF_TRACK_WIRED_CLIENTS,
    CONF_UNAUTHENTICATED_MODE,
    CONNECTION_TIMEOUT,
    DEFAULT_DEVICE_NAME,
    DEFAULT_NOTIFY_SERVICE_NAME,
    DEFAULT_TRACK_WIRED_CLIENTS,
    DEFAULT_UNAUTHENTICATED_MODE,
    DOMAIN,
)
from .utils import get_device_macs, non_verifying_requests_session

_LOGGER = logging.getLogger(__name__)


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Huawei LTE config flow."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get options flow."""
        return OptionsFlowHandler(config_entry)

    async def _async_show_user_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
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
                        CONF_VERIFY_SSL,
                        default=user_input.get(
                            CONF_VERIFY_SSL,
                            False,
                        ),
                    ): bool,
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

    async def _async_show_reauth_form(
        self,
        user_input: dict[str, Any],
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
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

    async def _connect(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> Connection | None:
        """Try connecting with given data."""
        username = user_input.get(CONF_USERNAME) or ""
        password = user_input.get(CONF_PASSWORD) or ""

        def _get_connection() -> Connection:
            if (
                user_input[CONF_URL].startswith("https://")
                and not user_input[CONF_VERIFY_SSL]
            ):
                requests_session = non_verifying_requests_session(user_input[CONF_URL])
            else:
                requests_session = None

            return Connection(
                url=user_input[CONF_URL],
                username=username,
                password=password,
                timeout=CONNECTION_TIMEOUT,
                requests_session=requests_session,
            )

        conn = None
        try:
            conn = await self.hass.async_add_executor_job(_get_connection)
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
        except SSLError:
            _LOGGER.warning("SSL error", exc_info=True)
            if user_input[CONF_VERIFY_SSL]:
                errors[CONF_URL] = "ssl_error_try_unverified"
            else:
                errors[CONF_URL] = "ssl_error_try_plain"
        except Timeout:
            _LOGGER.warning("Connection timeout", exc_info=True)
            errors[CONF_URL] = "connection_timeout"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.warning("Unknown error connecting to device", exc_info=True)
            errors[CONF_URL] = "unknown"
        return conn

    @staticmethod
    def _disconnect(conn: Connection) -> None:
        try:
            conn.close()
            conn.requests_session.close()
        except Exception:  # pylint: disable=broad-except
            _LOGGER.debug("Disconnect error", exc_info=True)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

        def get_device_info(
            conn: Connection,
        ) -> tuple[GetResponseType, GetResponseType]:
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

        conn = await self._connect(user_input, errors)
        if errors:
            return await self._async_show_user_form(
                user_input=user_input, errors=errors
            )
        assert conn

        info, wlan_settings = await self.hass.async_add_executor_job(
            get_device_info, conn
        )
        await self.hass.async_add_executor_job(self._disconnect, conn)

        user_input.update(
            {
                CONF_MAC: get_device_macs(info, wlan_settings),
                CONF_MANUFACTURER: self.context.get(CONF_MANUFACTURER),
            }
        )

        if not self.unique_id:
            if serial_number := info.get("SerialNumber"):
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured(updates=user_input)
            else:
                await self._async_handle_discovery_without_unique_id()

        title = (
            self.context.get("title_placeholders", {}).get(CONF_NAME)
            or info.get("DeviceName")  # device.information
            or info.get("devicename")  # device.basic_information
            or DEFAULT_DEVICE_NAME
        )

        return self.async_create_entry(title=title, data=user_input)

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP initiated config flow."""

        if TYPE_CHECKING:
            assert discovery_info.ssdp_location
        url = url_normalize(
            discovery_info.upnp.get(
                ssdp.ATTR_UPNP_PRESENTATION_URL,
                f"http://{urlparse(discovery_info.ssdp_location).hostname}/",
            )
        )

        unique_id = discovery_info.upnp.get(
            ssdp.ATTR_UPNP_SERIAL, discovery_info.upnp[ssdp.ATTR_UPNP_UDN]
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_URL: url})

        def _is_supported_device() -> bool:
            """See if we are looking at a possibly supported device.

            Matching solely on SSDP data does not yield reliable enough results.
            """
            try:
                with Connection(url=url, timeout=CONNECTION_TIMEOUT) as conn:
                    basic_info = Client(conn).device.basic_information()
            except ResponseErrorException:  # API compatible error
                return True
            except Exception:  # API incompatible error # pylint: disable=broad-except
                return False
            return isinstance(basic_info, dict)  # Crude content check

        if not await self.hass.async_add_executor_job(_is_supported_device):
            return self.async_abort(reason="unsupported_device")

        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
                },
                CONF_MANUFACTURER: discovery_info.upnp.get(ssdp.ATTR_UPNP_MANUFACTURER),
                CONF_URL: url,
            }
        )
        return await self._async_show_user_form()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry
        if not user_input:
            return await self._async_show_reauth_form(
                user_input={
                    CONF_USERNAME: entry.data[CONF_USERNAME],
                    CONF_PASSWORD: entry.data[CONF_PASSWORD],
                }
            )

        new_data = {**entry.data, **user_input}
        errors: dict[str, str] = {}
        conn = await self._connect(new_data, errors)
        if conn:
            await self.hass.async_add_executor_job(self._disconnect, conn)
        if errors:
            return await self._async_show_reauth_form(
                user_input=user_input, errors=errors
            )

        self.hass.config_entries.async_update_entry(entry, data=new_data)
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")


class OptionsFlowHandler(OptionsFlow):
    """Huawei LTE options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
