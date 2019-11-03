"""Config flow for the Huawei LTE platform."""

from collections import OrderedDict
import logging
from typing import Optional

from huawei_lte_api.AuthorizedConnection import AuthorizedConnection
from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection
from huawei_lte_api.exceptions import (
    LoginErrorUsernameWrongException,
    LoginErrorPasswordWrongException,
    LoginErrorUsernamePasswordWrongException,
    LoginErrorUsernamePasswordOverrunException,
    ResponseErrorException,
)
from requests.exceptions import Timeout
from url_normalize import url_normalize
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_RECIPIENT, CONF_URL, CONF_USERNAME
from homeassistant.core import callback
from .const import CONNECTION_TIMEOUT, DEFAULT_DEVICE_NAME

# https://github.com/PyCQA/pylint/issues/3202
from .const import DOMAIN  # pylint: disable=unused-import


_LOGGER = logging.getLogger(__name__)


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Huawei LTE config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow."""
        return OptionsFlowHandler(config_entry)

    async def _async_show_user_form(self, user_input=None, errors=None):
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                OrderedDict(
                    (
                        (
                            vol.Required(
                                CONF_URL, default=user_input.get(CONF_URL, "")
                            ),
                            str,
                        ),
                        (
                            vol.Optional(
                                CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                            ),
                            str,
                        ),
                        (
                            vol.Optional(
                                CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                            ),
                            str,
                        ),
                    )
                )
            ),
            errors=errors or {},
        )

    async def async_step_import(self, user_input=None):
        """Handle import initiated config flow."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
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

        # See if we already have a router configured with this URL
        existing_urls = {  # existing entries
            url_normalize(entry.data[CONF_URL], default_scheme="http")
            for entry in self._async_current_entries()
        }
        if user_input[CONF_URL] in existing_urls:
            return self.async_abort(reason="already_configured")

        conn = None

        def logout():
            if hasattr(conn, "user"):
                try:
                    conn.user.logout()
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.debug("Could not logout", exc_info=True)

        def try_connect(username: Optional[str], password: Optional[str]) -> Connection:
            """Try connecting with given credentials."""
            if username or password:
                conn = AuthorizedConnection(
                    user_input[CONF_URL],
                    username=username,
                    password=password,
                    timeout=CONNECTION_TIMEOUT,
                )
            else:
                try:
                    conn = AuthorizedConnection(
                        user_input[CONF_URL],
                        username="",
                        password="",
                        timeout=CONNECTION_TIMEOUT,
                    )
                    user_input[CONF_USERNAME] = ""
                    user_input[CONF_PASSWORD] = ""
                except ResponseErrorException:
                    _LOGGER.debug(
                        "Could not login with empty credentials, proceeding unauthenticated",
                        exc_info=True,
                    )
                    conn = Connection(user_input[CONF_URL], timeout=CONNECTION_TIMEOUT)
                    del user_input[CONF_USERNAME]
                    del user_input[CONF_PASSWORD]
            return conn

        def get_router_title(conn: Connection) -> str:
            """Get title for router."""
            title = None
            client = Client(conn)
            try:
                info = client.device.basic_information()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Could not get device.basic_information", exc_info=True)
            else:
                title = info.get("devicename")
            if not title:
                try:
                    info = client.device.information()
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.debug("Could not get device.information", exc_info=True)
                else:
                    title = info.get("DeviceName")
            return title or DEFAULT_DEVICE_NAME

        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)
        try:
            conn = await self.hass.async_add_executor_job(
                try_connect, username, password
            )
        except LoginErrorUsernameWrongException:
            errors[CONF_USERNAME] = "incorrect_username"
        except LoginErrorPasswordWrongException:
            errors[CONF_PASSWORD] = "incorrect_password"
        except LoginErrorUsernamePasswordWrongException:
            errors[CONF_USERNAME] = "incorrect_username_or_password"
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
            errors[CONF_URL] = "unknown_connection_error"
        if errors:
            await self.hass.async_add_executor_job(logout)
            return await self._async_show_user_form(
                user_input=user_input, errors=errors
            )

        title = await self.hass.async_add_executor_job(get_router_title, conn)
        await self.hass.async_add_executor_job(logout)

        return self.async_create_entry(title=title, data=user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Huawei LTE options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_RECIPIENT,
                    default=self.config_entry.options.get(CONF_RECIPIENT, ""),
                ): str
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
