"""OpenTherm Gateway config flow."""
import asyncio
from serial import SerialException

import pyotgw
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import (
    CONF_DEVICE,
    CONF_ID,
    CONF_NAME,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)

import homeassistant.helpers.config_validation as cv

from . import DOMAIN
from .const import CONF_FLOOR_TEMP, CONF_PRECISION


class OpenThermGwConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """OpenTherm Gateway Config Flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_init(self, info=None):
        """Handle config flow initiation."""
        if info:
            name = info[CONF_NAME]
            device = info[CONF_DEVICE]
            gw_id = info.get(CONF_ID, cv.slugify(name))
            precision = info.get(CONF_PRECISION)
            floor_temp = info[CONF_FLOOR_TEMP]

            entries = {
                k: v
                for e in self.hass.config_entries.async_entries(DOMAIN)
                for k, v in e.data.items()
            }

            if gw_id in entries:
                return self._show_form({"base": "id_exists"})

            if device in [e[CONF_DEVICE] for e in entries.values()]:
                return self._show_form({"base": "already_configured"})

            async def test_connection():
                """Try to connect to the OpenTherm Gateway."""
                otgw = pyotgw.pyotgw()
                status = await otgw.connect(self.hass.loop, device)
                await otgw.disconnect()
                return status.get(pyotgw.OTGW_ABOUT)

            try:
                res = await asyncio.wait_for(test_connection(), timeout=10)
            except asyncio.TimeoutError:
                return self._show_form({"base": "timeout"})
            except SerialException:
                return self._show_form({"base": "serial_error"})

            if res:
                return self._create_entry(gw_id, name, device, precision, floor_temp)

        return self._show_form()

    async def async_step_user(self, info=None):
        """Handle manual initiation of the config flow."""
        return await self.async_step_init(info)

    async def async_step_import(self, import_config):
        """
        Import an OpenTherm Gateway device as a config entry.

        This flow is triggered by `async_setup` for configured devices.
        """
        climate_config = import_config.get(CLIMATE_DOMAIN, {})
        formatted_config = {
            CONF_NAME: import_config.get(CONF_NAME, import_config[CONF_ID]),
            CONF_DEVICE: import_config[CONF_DEVICE],
            CONF_ID: import_config[CONF_ID],
            CONF_PRECISION: climate_config.get(CONF_PRECISION),
            CONF_FLOOR_TEMP: climate_config.get(CONF_FLOOR_TEMP, False),
        }
        return await self.async_step_init(info=formatted_config)

    def _show_form(self, errors=None):
        """Show the config flow form with possible errors."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_DEVICE): str,
                    vol.Optional(CONF_ID): str,
                    vol.Optional(CONF_PRECISION): vol.All(
                        vol.Coerce(float),
                        vol.In([PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]),
                    ),
                    vol.Optional(CONF_FLOOR_TEMP, default=False): bool,
                }
            ),
            errors=errors,
        )

    def _create_entry(self, gw_id, name, device, precision, floor_temp):
        """Create entry for the OpenTherm Gateway device."""
        return self.async_create_entry(
            title="OpenTherm Gateway",
            data={
                gw_id: {
                    CONF_DEVICE: device,
                    CONF_NAME: name,
                    CLIMATE_DOMAIN: {
                        CONF_PRECISION: precision,
                        CONF_FLOOR_TEMP: floor_temp,
                    },
                }
            },
        )
