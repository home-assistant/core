"""Config flow for Klyqa."""

from typing import Any, cast
from numpy import integer

from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from klyqa_ctl import klyqa_ctl as api

from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry

from .datacoordinator import HAKlyqaAccount, KlyqaDataCoordinator

from .const import CONF_POLLING, DOMAIN, LOGGER, CONF_SYNC_ROOMS
import homeassistant.helpers.config_validation as cv

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult

user_step_data_schema = {
    vol.Required(CONF_USERNAME, default=""): cv.string,
    vol.Required(CONF_PASSWORD, default=""): cv.string,
    vol.Required(CONF_SCAN_INTERVAL, default=60): int,
    vol.Required(CONF_SYNC_ROOMS, default=True, msg="sync r", description="sync R"): bool,
    vol.Required(CONF_POLLING, default=True): bool,
    vol.Required(CONF_HOST, default="https://app-api.prod.qconnex.io"): str,
}


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            self.username = str(user_input[CONF_USERNAME])
            self.password = str(user_input[CONF_PASSWORD])
            self.scan_interval = int(user_input[CONF_SCAN_INTERVAL])
            self.sync_rooms = user_input[CONF_SYNC_ROOMS]
            self.polling = user_input[CONF_POLLING]
            self.host = str(user_input[CONF_HOST])
            return await self._async_klyqa_login(step_id="user")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self.config_entry.data[CONF_USERNAME]): cv.string,
                    vol.Required(CONF_PASSWORD, default=self.config_entry.data[CONF_PASSWORD]): cv.string,
                    vol.Required(CONF_POLLING, default=self.config_entry.data[CONF_POLLING]): bool,
                    vol.Required(CONF_SCAN_INTERVAL, default=self.config_entry.data[CONF_SCAN_INTERVAL]): int,
                    vol.Required(CONF_SYNC_ROOMS, default=self.config_entry.data[CONF_SYNC_ROOMS]): bool,
                    vol.Required(CONF_HOST, default=self.config_entry.data[CONF_HOST]): str,
                }
            ),
        )

    async def _async_klyqa_login(self, step_id: str) -> FlowResult:
        """Handle login with Klyqa."""
        errors = {}

        try:
            klyqa: HAKlyqaAccount = HAKlyqaAccount(
                None,
                None,
                self.username,
                self.password,
                self.host,
                self.hass,
                sync_rooms=self.sync_rooms,
                polling=self.polling,
                scan_interval = self.scan_interval
            )
            if not await self.hass.async_run_job(
                klyqa.login,
            ):
                raise Exception("Unable to login")
            self.klyqa = klyqa

        except Exception as ex:

            LOGGER.error("Unable to connect to Klyqa: %s", ex)
            errors = {"base": "cannot_connect"}

        if not self.klyqa or not self.klyqa.access_token:
            errors = {"base": "cannot_connect"}

        if errors:
            return await self._show_setup_form(errors)

        return await self._async_create_entry()

    async def _async_create_entry(self) -> FlowResult:
        """Create the config entry."""
        config_data = {
            CONF_USERNAME: self.username,
            CONF_PASSWORD: self.password,
            CONF_SCAN_INTERVAL: self.scan_interval,
            CONF_SYNC_ROOMS: self.sync_rooms,
            CONF_POLLING: self.polling,
            CONF_HOST: self.host,
        }

        return self.async_create_entry(
            title=cast(str, self.username), data=config_data
        )


class KlyqaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    # (this is not implemented yet)
    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""

        self.inited = False
        self.username: str | None = None
        self.password: str | None = None
        self.cache: str | None = None
        self.scan_interval: int = 30
        self.host: str | None = None
        self.sync_rooms: bool | None = None
        self.polling: bool | None = None
        self.klyqa: HAKlyqaAccount = None
        pass

    async def init(self):
        if self.inited:
            return
        self.inited = True
        integration_data, cached = await api.async_json_cache(
            None, "last.klyqa_integration_data.cache.json"
        )
        if cached:

            self.username = str(integration_data[CONF_USERNAME])
            self.password = str(integration_data[CONF_PASSWORD])
            self.scan_interval = int(integration_data[CONF_SCAN_INTERVAL])
            self.host = str(integration_data[CONF_HOST])
            self.sync_rooms = bool(integration_data[CONF_SYNC_ROOMS])
            self.polling = bool(integration_data[CONF_POLLING])

    def get_klyqa(self) -> HAKlyqaAccount:
        if self.klyqa:
            return self.klyqa
        if not self.hass or not DOMAIN in self.hass.data or not self.hass.data[DOMAIN].KlyqaAccounts or not len(self.hass.data[DOMAIN].KlyqaAccounts):
            return None
        self.klyqa = self.hass.data[DOMAIN].KlyqaAccounts[0]
        return self.klyqa

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self.username): cv.string,
                    vol.Required(CONF_PASSWORD, default=self.password): cv.string,
                    vol.Required(CONF_POLLING, default=self.polling): bool,
                    vol.Required(CONF_SCAN_INTERVAL, default=self.scan_interval): int,
                    vol.Required(CONF_SYNC_ROOMS, default=self.sync_rooms): bool,
                    vol.Required(CONF_HOST, default=self.host): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        """ already logged in from platform or other way """
        if self.get_klyqa():
            return self.async_abort(reason="single_instance_allowed")

        await self.init()

        login_failed = False

        if user_input is None or login_failed:
            return await self._show_setup_form()

        self.username = str(user_input[CONF_USERNAME])
        self.password = str(user_input[CONF_PASSWORD])
        self.scan_interval = int(user_input[CONF_SCAN_INTERVAL])
        self.sync_rooms = user_input[CONF_SYNC_ROOMS]
        self.polling = user_input[CONF_POLLING]
        self.host = str(user_input[CONF_HOST])

        return await self._async_klyqa_login(step_id="user")

    async def _async_klyqa_login(self, step_id: str) -> FlowResult:
        """Handle login with Klyqa."""
        errors = {}

        try:

            klyqa: HAKlyqaAccount = HAKlyqaAccount(
                None,
                None,
                self.username,
                self.password,
                self.host,
                self.hass,
                sync_rooms=self.sync_rooms,
                polling=self.polling,
                scan_interval = self.scan_interval
            )
            if not await self.hass.async_run_job(
                klyqa.login,
            ):
                raise Exception("Unable to login")
            self.klyqa = klyqa

        except (ConnectTimeout, HTTPError):
            LOGGER.error("Unable to connect to Klyqa: %s", ex)
            errors = {"base": "cannot_connect"}

        except Exception as ex:

            LOGGER.error("Unable to connect to Klyqa: %s", ex)
            errors = {"base": "cannot_connect"}

        if not self.klyqa or not self.klyqa.access_token:
            errors = {"base": "cannot_connect"}

        if errors:
            return await self._show_setup_form(errors)

        return await self._async_create_entry()

    async def _async_create_entry(self) -> FlowResult:
        """Create the config entry."""
        config_data = {
            CONF_USERNAME: self.username,
            CONF_PASSWORD: self.password,
            CONF_SCAN_INTERVAL: self.scan_interval,
            CONF_SYNC_ROOMS: self.sync_rooms,
            CONF_POLLING: self.polling,
            CONF_HOST: self.host,
        }
        existing_entry = await self.async_set_unique_id(self.username)

        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry, data=config_data
            )
            # Reload the Klyqa config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=cast(str, self.username), data=config_data
        )

    # @staticmethod
    # @callback
    # def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
    #     """Get the options flow for this handler."""
    #     return OptionsFlowHandler(config_entry)