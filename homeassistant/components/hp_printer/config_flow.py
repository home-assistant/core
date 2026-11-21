"""Config flow for the HP Printer integration."""

from typing import Any, override

from aiohpprinter import HpPrinter, HpPrinterDevice, HpPrinterError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, SECTION_ADVANCED_SETTINGS

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(SECTION_ADVANCED_SETTINGS): section(
            probatio.Schema(
                {
                    probatio.Required(CONF_SSL, default=False): BooleanSelector(),
                    probatio.Optional(CONF_PORT): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=65535, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            {"collapsed": True},
        ),
    }
)


def _entry_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return the config entry data for the submitted form."""
    data = {
        CONF_HOST: user_input[CONF_HOST],
        **user_input[SECTION_ADVANCED_SETTINGS],
    }
    if CONF_PORT in data:
        data[CONF_PORT] = int(data[CONF_PORT])
    return data


class HpPrinterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HP Printer."""

    MINOR_VERSION = 2

    _host: str
    _title: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _entry_data(user_input)
            device = await self._async_get_device(
                data[CONF_HOST], data.get(CONF_PORT), data[CONF_SSL]
            )
            if device is None:
                errors["base"] = "cannot_connect"
            else:
                if not device.serial_number:
                    return self.async_abort(reason="missing_serial_number")
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device.make_and_model or data[CONF_HOST],
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a printer discovered via zeroconf."""
        self._host = discovery_info.host
        self._async_abort_entries_match({CONF_HOST: self._host})

        device = await self._async_get_device(self._host, None, False)
        if device is None:
            return self.async_abort(reason="cannot_connect")
        if not device.serial_number:
            return self.async_abort(reason="missing_serial_number")

        await self.async_set_unique_id(device.serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self._title = device.make_and_model or self._host
        self.context["title_placeholders"] = {"name": self._title}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered printer."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._title, data={CONF_HOST: self._host, CONF_SSL: False}
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._title, "host": self._host},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the printer's connection settings."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            data = _entry_data(user_input)
            device = await self._async_get_device(
                data[CONF_HOST], data.get(CONF_PORT), data[CONF_SSL]
            )
            if device is None:
                errors["base"] = "cannot_connect"
            else:
                if not device.serial_number:
                    return self.async_abort(reason="missing_serial_number")
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(reconfigure_entry, data=data)

        entry_data = reconfigure_entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input
                or {
                    CONF_HOST: entry_data[CONF_HOST],
                    SECTION_ADVANCED_SETTINGS: {
                        key: entry_data[key]
                        for key in (CONF_SSL, CONF_PORT)
                        if key in entry_data
                    },
                },
            ),
            errors=errors,
        )

    async def _async_get_device(
        self, host: str, port: int | None, ssl: bool
    ) -> HpPrinterDevice | None:
        """Return the printer's identity, or None if it cannot be reached."""
        client = HpPrinter(host, async_get_clientsession(self.hass), port=port, ssl=ssl)
        try:
            device = await client.device()
            # Updates fail without the status endpoint, so check it too.
            await client.status()
        except HpPrinterError:
            return None
        return device
