"""Config flow for Kostal Piko solar inverters."""
import logging
from typing import Any

import kostal
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SETUP_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOST, description={"suggested_value": "http://192.168.178.xyz"}
        ): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def test_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str, str, str]:
    """Tests the connection to the inverter and returns its name."""
    session = async_get_clientsession(hass)
    inverter = kostal.Piko(session, data["host"], data["username"], data["password"])
    res = await inverter.fetch_props(
        kostal.SettingsGeneral.INVERTER_NAME,
        kostal.SettingsGeneral.INVERTER_MAKE,
        kostal.InfoVersions.SERIAL_NUMBER,
    )

    name_entry = res.get_entry_by_id(kostal.SettingsGeneral.INVERTER_NAME)
    make_entry = res.get_entry_by_id(kostal.SettingsGeneral.INVERTER_MAKE)
    serial_entry = res.get_entry_by_id(kostal.InfoVersions.SERIAL_NUMBER)

    name = name_entry.value if name_entry is not None else ""
    make = make_entry.value if make_entry is not None else ""
    serial = serial_entry.value if serial_entry is not None else ""

    return (name, make, serial)


class KostalPikoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the Kostal Piko inverter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user initiating the flow via the user interface."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                name, make, serial = await test_connection(self.hass, user_input)
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"{make} {name} ({serial})", data=user_input
                )

            except ValueError as err:
                _LOGGER.error("Kostal Piko setup failed: %s", err)
                errors[CONF_HOST] = "not_specified"
            except ConnectionError as err:
                _LOGGER.error("Could not connect to Kostal Piko api: %s", err)
                errors[CONF_HOST] = "cannot_connect"
            except AbortFlow:
                _LOGGER.info("Flow aborted, unique id already configured")
                raise
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                errors[CONF_BASE] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=SETUP_SCHEMA, errors=errors
        )
