"""Config flow for Kuler Sky."""
import logging

import pykulersky
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Kuler Sky"


class KulerSkyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Kuler sky config flow."""

    async def async_step_user(self, user_input=None):
        """Search for nearby lights and prompt user."""
        errors = {}

        if user_input is not None:
            address, name = user_input["device"].split(" ", 1)

            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            # Ensure the light can connect
            light = pykulersky.Light(address, name)
            try:
                await self.hass.async_add_executor_job(light.connect)
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ADDRESS: address,
                        CONF_NAME: name,
                    },
                )
            except pykulersky.PykulerskyException:
                errors["device"] = "cannot_connect"

        try:
            devices = await self.hass.async_add_executor_job(pykulersky.discover)
        except pykulersky.PykulerskyException as exc:
            _LOGGER.error("Exception scanning for Kuler Sky devices", exc_info=exc)
            return self.async_abort(reason="scan_error")

        options = [
            "{} {}".format(device["address"], device["name"]) for device in devices
        ]

        default_device = None if user_input is None else user_input["device"]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("device", default=default_device): vol.In(options),
                }
            ),
            errors=errors,
        )
