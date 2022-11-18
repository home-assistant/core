"""Config flow for Kostal Piko solar inverters."""
import logging

import kostal
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SETUP_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOST, description={"suggested_valed": "http://192.168.178.xyz"}
        ): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def test_connection(hass: HomeAssistant, data) -> tuple[str, str, str]:
    """Tests the connection to the inverter and returns its name."""
    session = async_get_clientsession(hass)
    inverter = kostal.Piko(session, data["host"], data["username"], data["password"])
    res = await inverter.fetch_props(
        kostal.SettingsGeneral.INVERTER_NAME,
        kostal.SettingsGeneral.INVERTER_MAKE,
        kostal.InfoVersions.SERIAL_NUMBER,
    )
    name = res.get_entry_by_id(kostal.SettingsGeneral.INVERTER_NAME).value
    make = res.get_entry_by_id(kostal.SettingsGeneral.INVERTER_MAKE).value
    serial = res.get_entry_by_id(kostal.InfoVersions.SERIAL_NUMBER).value

    return (name, make, serial)


class KostalPikoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the Kostal Piko inverter."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the user initiating the flow via the user interface."""
        errors = {}

        if user_input is not None:
            try:
                name, make, serial = await test_connection(self.hass, user_input)
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

            except ValueError as err:
                _LOGGER.error("Kostal Piko api returned unknown value: %s", err)
                errors[CONF_BASE] = "unknown"
            except ConnectionError as err:
                _LOGGER.error("Could not connect to Kostal Piko api: %s", err)
                errors[CONF_HOST] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                errors[CONF_BASE] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=f"{make} {name} ({serial})", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=SETUP_SCHEMA, errors=errors
        )
