"""ConfigFlow for EGPS devices."""
from typing import Any

from pyegps import get_device, search_for_devices
from pyegps.exceptions import MissingLibrary, UsbError
import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_DEVICE_API_ID, DOMAIN, LOGGER


class ConfigFLow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for EGPM devices."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initiate user flow."""

        if user_input is not None:
            if CONF_DEVICE_API_ID in user_input:
                devId = user_input[CONF_DEVICE_API_ID]
                dev = get_device(device_id=devId)
                if dev is not None:
                    await self.async_set_unique_id(dev.device_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"{devId}",
                        data={CONF_DEVICE_API_ID: devId},
                    )
            return self.async_abort(reason="device_not_found")

        currently_configured = self._async_current_ids(include_ignore=True)
        try:
            found_devices = search_for_devices()
        except (MissingLibrary, UsbError) as err:
            LOGGER.error("Unable to access USB devices: %s", err)
            return self.async_abort(reason="usb_error")

        devices = [
            d
            for d in found_devices
            if d.get_device_type() == "PowerStrip"
            and d.device_id not in currently_configured
        ]
        if len(devices) > 0:
            options = {d.device_id: f"{d.name} ({d.device_id})" for d in devices}
            data_schema = {CONF_DEVICE_API_ID: vol.In(options)}
        else:
            return self.async_abort(reason="no_device")

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))
