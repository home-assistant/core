"""ConfigFlow for Energenie-Power-Sockets devices."""

from typing import Any

from pyegps import get_device, search_for_devices
from pyegps.exceptions import MissingLibrary, UsbError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_DEVICE_API_ID, DOMAIN, LOGGER


class EGPSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for EGPS devices."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initiate user flow."""

        if user_input is not None:
            dev_id = user_input[CONF_DEVICE_API_ID]
            dev = await self.hass.async_add_executor_job(get_device, dev_id)
            if dev is not None:
                await self.async_set_unique_id(dev.device_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=dev_id,
                    data={CONF_DEVICE_API_ID: dev_id},
                )
            return self.async_abort(reason="device_not_found")

        currently_configured = self._async_current_ids(include_ignore=True)
        try:
            found_devices = await self.hass.async_add_executor_job(search_for_devices)
        except (MissingLibrary, UsbError):
            LOGGER.exception("Unable to access USB devices")
            return self.async_abort(reason="usb_error")

        devices = [
            d
            for d in found_devices
            if d.get_device_type() == "PowerStrip"
            and d.device_id not in currently_configured
        ]
        LOGGER.debug("Found %d devices", len(devices))
        if len(devices) > 0:
            options = {d.device_id: f"{d.name} ({d.device_id})" for d in devices}
            data_schema = {CONF_DEVICE_API_ID: vol.In(options)}
        else:
            return self.async_abort(reason="no_device")

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))
