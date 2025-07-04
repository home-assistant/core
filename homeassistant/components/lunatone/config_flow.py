"""Config flow for Lunatone."""

from __future__ import annotations

import asyncio
from enum import StrEnum
import logging
from typing import Any, Final

import aiohttp
from lunatone_dali_api_client import Auth, DALIScan, Info
from lunatone_dali_api_client.models import ScanState, StartScanData
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_URL
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DALIDeviceScanMethod(StrEnum):
    """DALI device scan methods."""

    DO_NOTHING = "do_nothing"
    CURRENT_DEVICE_LIST = "current_device_list"
    SYSTEM_EXTENSION = "system_extension"
    NEW_INSTALLATION = "new_installation"


DEFAULT_DALI_DEVICE_SCAN_METHOD: Final = DALIDeviceScanMethod.DO_NOTHING
DALI_DEVICE_SCAN_METHODS: Final[list[str]] = [
    option.value for option in DALIDeviceScanMethod
]

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_URL, default="http://"): cv.string},
)
RECONFIGURE_SCHEMA = DATA_SCHEMA
DALI_SCAN_SCHEMA = vol.Schema(
    {
        vol.Required(
            "device_scan_method", default=DEFAULT_DALI_DEVICE_SCAN_METHOD
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=DALI_DEVICE_SCAN_METHODS,
                translation_key="device_scan_method",
                mode=selector.SelectSelectorMode.LIST,
            ),
        ),
    }
)


class LunatoneDALIIoTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Lunatone DALI IoT config flow."""

    VERSION = 0
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.url: str | None = None
        self.name: str | None = None
        self.serial_number: int | None = None
        self.dali_device_scan_task: asyncio.Task | None = None

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
                    return await self.async_step_dali()
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
            last_step=bool(self.source == SOURCE_RECONFIGURE),
        )

    def _create_entry(self) -> ConfigFlowResult:
        """Return a config entry for the flow."""
        assert self.url is not None
        return self.async_create_entry(
            title=self._title,
            data={CONF_URL: self.url},
        )

    async def async_step_dali(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow that does DALI related stuff."""
        step_id = "dali"
        errors: dict[str, str] = {}
        if user_input is not None:
            method = user_input["device_scan_method"]
            if method == DALIDeviceScanMethod.DO_NOTHING:  # Skip device scan
                return self._create_entry()
            if not self.dali_device_scan_task:
                self.dali_device_scan_task = self.hass.async_create_task(
                    self._async_start_dali_device_scan(method)
                )
            if not self.dali_device_scan_task.done():
                return self.async_show_progress(
                    step_id=step_id,
                    progress_action="device_scan",
                    progress_task=self.dali_device_scan_task,
                )

        if self.dali_device_scan_task:
            self.dali_device_scan_task = None
            return self.async_show_progress_done(next_step_id="finish")
        return self.async_show_form(
            step_id=step_id,
            data_schema=DALI_SCAN_SCHEMA,
            errors=errors,
            last_step=False,
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle finishing the config flow."""
        if user_input is not None:
            return self._create_entry()
        return self.async_show_form()

    async def _async_start_dali_device_scan(self, method: DALIDeviceScanMethod) -> None:
        auth = Auth(
            session=async_get_clientsession(self.hass),
            base_url=self.url,
        )
        scan = DALIScan(auth)
        await scan.async_update()

        if scan.data.status in {ScanState.ADDRESSING, ScanState.IN_PROGRESS}:
            await self._async_is_dali_device_scan_done(scan)

        if method == DALIDeviceScanMethod.SYSTEM_EXTENSION:
            start_scan_data = StartScanData()
        elif method == DALIDeviceScanMethod.NEW_INSTALLATION:
            start_scan_data = StartScanData(newInstallation=True)
        else:
            start_scan_data = StartScanData(noAddressing=True)

        await scan.async_start(start_scan_data)
        await self._async_is_dali_device_scan_done(scan)

    async def _async_is_dali_device_scan_done(self, scan: DALIScan) -> None:
        for _ in range(120):
            await scan.async_update()
            if scan.data.status == ScanState.DONE:
                return
            await asyncio.sleep(5)
        raise RuntimeError("DALI device scan ran for a long time and never finished")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self.async_step_user(user_input)
