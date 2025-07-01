"""Config flow for Lunatone."""

import asyncio
from enum import StrEnum
import logging
from typing import Any, Final
from urllib.parse import urlparse

import aiohttp
from lunatone_dali_api_client import Auth, DALIScan, Info
from lunatone_dali_api_client.models import ScanState, StartScanData
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_URL, default="http://"): cv.string},
)
RECONFIGURE_SCHEMA = DATA_SCHEMA


class DeviceScanMethod(StrEnum):
    """Device scan methods."""

    CURRENT_DEVICE_LIST = "current_device_list"
    SYSTEM_EXTENSION = "system_extension"
    NEW_INSTALLATION = "new_installation"


DEFAULT_DEVICE_SCAN_METHOD: Final = DeviceScanMethod.CURRENT_DEVICE_LIST
DEVICE_SCAN_METHODS: Final[list[str]] = [option.value for option in DeviceScanMethod]


class LunatoneDALIIoTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Lunatone DALI IoT config flow."""

    VERSION = 0
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.url: str | None = None
        self.name: str | None = None
        self.serial_number: int | None = None

    @property
    def _title(self):
        return f"{self.name or 'DALI Gateway'} {self.serial_number}"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.url = user_input[CONF_URL]
            data = {CONF_URL: self.url}
            self._async_abort_entries_match(data)
            auth = Auth(
                session=async_get_clientsession(self.hass),
                base_url=self.url,
            )
            info = Info(auth)
            try:
                await info.async_update()
            except aiohttp.InvalidUrlClientError:
                _LOGGER.debug(("Invalid URL: %s"), self.url)
                errors["base"] = "invalid_url"
            except aiohttp.ClientConnectionError:
                _LOGGER.debug(
                    (
                        "Failed to connect to device %s. Check the URL and if the "
                        "device is connected to power"
                    ),
                    self.url,
                )
                errors["base"] = "cannot_connect"
            else:
                self.name = info.data.name
                self.serial_number = info.data.device.serial
                await self.async_set_unique_id(str(self.serial_number))
                if self.source == SOURCE_USER:
                    self._abort_if_unique_id_configured()
                    return self._create_entry()
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=data,
                    title=self._title,
                )

        step_id = "reconfigure"
        data_schema = RECONFIGURE_SCHEMA
        if self.source == SOURCE_USER:
            step_id = "user"
            data_schema = DATA_SCHEMA
        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors,
        )

    def _create_entry(self) -> ConfigFlowResult:
        """Return a config entry for the flow."""
        assert self.url is not None
        return self.async_create_entry(
            title=self._title,
            data={CONF_URL: self.url},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Lunatone DALI IoT options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.device_scan_task: asyncio.Task | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            method = user_input["device_scan_method"]
            if not self.device_scan_task:
                self.device_scan_task = self.hass.async_create_task(
                    self._async_device_scan(method)
                )
        if self.device_scan_task:
            if not self.device_scan_task.done():
                return self.async_show_progress(
                    progress_action="device_scan",
                    progress_task=self.device_scan_task,
                )
            self.device_scan_task = None
            return self.async_show_progress_done(next_step_id="finish")
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "device_scan_method", default=DEFAULT_DEVICE_SCAN_METHOD
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=DEVICE_SCAN_METHODS,
                            translation_key="device_scan_method",
                            mode=selector.SelectSelectorMode.LIST,
                        ),
                    ),
                }
            ),
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device scan."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form()

    async def _async_device_scan(self, method: DeviceScanMethod) -> None:
        auth = Auth(
            session=async_get_clientsession(self.hass),
            base_url=self.config_entry.data[CONF_URL],
        )
        scan = DALIScan(auth)

        start_scan_data = None
        if method == DeviceScanMethod.CURRENT_DEVICE_LIST:
            start_scan_data = StartScanData(noAddressing=True)
        elif method == DeviceScanMethod.SYSTEM_EXTENSION:
            start_scan_data = StartScanData()
        elif method == DeviceScanMethod.NEW_INSTALLATION:
            start_scan_data = StartScanData(newInstallation=True)

        if start_scan_data is None:
            return
        await scan.async_start(start_scan_data)
        await scan.async_update()

        for _ in range(360):
            if scan.data.status == ScanState.DONE:
                return
            await asyncio.sleep(5)
            await scan.async_update()
        raise RuntimeError
