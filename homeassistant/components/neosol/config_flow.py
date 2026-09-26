"""Config flow for the Profalux Neosol integration."""

from typing import Any, override

import probatio
from pyneosol import DongleInfo, NeosolError, NotADongleError

from homeassistant.components import usb
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers.selector import SerialPortSelector
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import DOMAIN, LOGGER
from .coordinator import open_dongle

STEP_PORT_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_DEVICE): SerialPortSelector()}
)

TITLE = "Profalux Neosol"


class NeosolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Profalux Neosol."""

    VERSION = 1

    _discovered_port: str
    _info: DongleInfo

    async def _async_probe(self, port: str) -> str | None:
        """Read the dongle on ``port``, keeping its info, or return an error key.

        The dongle is closed again right away: the config entry setup is what owns the
        serial port, and it can only be opened once.
        """
        try:
            dongle, info = await open_dongle(port)
        except NotADongleError:
            return "not_a_dongle"
        except NeosolError:
            return "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return "unknown"

        await dongle.close()
        self._info = info
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a dongle configured by hand."""
        errors: dict[str, str] = {}

        if user_input is not None:
            port = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, user_input[CONF_DEVICE]
            )
            # The port is not opened exclusively: probing one a configured dongle
            # already uses would talk over it.
            self._async_abort_entries_match({CONF_DEVICE: port})

            if (error := await self._async_probe(port)) is None:
                await self.async_set_unique_id(self._info.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=TITLE, data={CONF_DEVICE: port})

            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_PORT_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    @override
    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle a dongle plugged into the host."""
        port = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )
        self._async_abort_entries_match({CONF_DEVICE: port})

        # The USB vendor id belongs to Silicon Labs and is shared by unrelated serial
        # adapters, so only the AT&V answer tells a dongle from anything else.
        if (error := await self._async_probe(port)) is not None:
            return self.async_abort(reason=error)

        await self.async_set_unique_id(self._info.serial_number)
        self._abort_if_unique_id_configured()
        self._discovered_port = port
        self._set_confirm_only()
        return await self.async_step_usb_confirm()

    async def async_step_usb_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered dongle."""
        if user_input is not None:
            return self.async_create_entry(
                title=TITLE, data={CONF_DEVICE: self._discovered_port}
            )

        return self.async_show_form(step_id="usb_confirm")
