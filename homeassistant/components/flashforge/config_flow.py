"""Config flow for FlashForge 3D Printer."""
from ffpp.Printer import Printer
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SERIAL_NUMBER, DOMAIN

'''
async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
# TODO Check if there are any devices that can be discovered in the network.
    devices = await hass.async_add_executor_job(ffpp.Printer.discover)
    return len(devices) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "FlashForge 3D Printer", _async_has_devices
)
'''


class FlashForgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow."""

    VERSION = 1

    ip_addr: str
    port: int
    serial: str
    machine_type: str
    printer: Printer

    async def async_step_user(self, user_input=None):
        """Run when user trying to add component."""
        # Default values.
        errors = {}
        port = 8899
        ip_addr = None

        # Validate user data
        if user_input is not None:

            # Update fields to the last state.
            self.ip_addr = user_input[CONF_IP_ADDRESS]
            self.port = user_input[CONF_PORT]

            try:
                await self._get_printer_info(self.hass, user_input)

                return self._async_create_entry()
            except CannotConnect:
                errors[CONF_IP_ADDRESS] = "cannot_connect"

        # The form fields to be presented in the form.
        data_schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS, default=ip_addr): str,
                vol.Optional(CONF_PORT, default=port): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def _get_printer_info(self, hass: HomeAssistant, data: dict) -> None:
        """Try to get info from given ip."""

        self.printer = Printer(self.ip_addr, self.port)

        try:
            await self.printer.connect()
        except TimeoutError as err:
            raise CannotConnect(err) from err
        except ConnectionError as err:
            raise CannotConnect(err) from err

        if self.printer.serial is not None:
            await self.async_set_unique_id(self.printer.serial)

        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: self.ip_addr, CONF_PORT: self.port}
        )

    @callback
    def _async_create_entry(self) -> FlowResult:
        return self.async_create_entry(
            title=self.printer.machine_name,
            data={
                CONF_IP_ADDRESS: self.ip_addr,
                CONF_PORT: self.port,
                CONF_SERIAL_NUMBER: self.printer.serial,
            },
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
