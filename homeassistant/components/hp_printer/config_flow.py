"""Config flow for the HP Printer integration."""

from typing import Any, override

from aiohpprinter import HpPrinter, HpPrinterDevice, HpPrinterError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
    }
)


class HpPrinterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HP Printer."""

    _host: str
    _title: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device = await self._async_get_device(user_input[CONF_HOST])
            if device is None:
                errors["base"] = "cannot_connect"
            else:
                if not device.serial_number:
                    return self.async_abort(reason="missing_serial_number")
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device.make_and_model or user_input[CONF_HOST],
                    data=user_input,
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

        device = await self._async_get_device(self._host)
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
                title=self._title, data={CONF_HOST: self._host}
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._title, "host": self._host},
        )

    async def _async_get_device(self, host: str) -> HpPrinterDevice | None:
        """Return the printer's identity, or None if it cannot be reached."""
        client = HpPrinter(host, async_get_clientsession(self.hass))
        try:
            device = await client.device()
            # Updates fail without the status endpoint, so check it too.
            await client.status()
        except HpPrinterError:
            return None
        return device
