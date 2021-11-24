"""Config flow for Fronius integration."""
from __future__ import annotations

import logging
from typing import Any

from pyfronius import Fronius, FroniusError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_RESOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, FroniusConfigEntryData

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str, FroniusConfigEntryData]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]
    fronius = Fronius(async_get_clientsession(hass), host)

    try:
        datalogger_info: dict[str, Any]
        datalogger_info = await fronius.current_logger_info()
    except FroniusError as err:
        _LOGGER.debug(err)
    else:
        logger_uid: str = datalogger_info["unique_identifier"]["value"]
        return logger_uid, FroniusConfigEntryData(
            host=host,
            is_logger=True,
        )
    # Gen24 devices don't provide GetLoggerInfo
    try:
        inverter_info = await fronius.inverter_info()
        first_inverter = next(inverter for inverter in inverter_info["inverters"])
    except FroniusError as err:
        _LOGGER.debug(err)
        raise CannotConnect from err
    except StopIteration as err:
        raise CannotConnect("No supported Fronius SolarNet device found.") from err
    first_inverter_uid: str = first_inverter["unique_id"]["value"]
    return first_inverter_uid, FroniusConfigEntryData(
        host=host,
        is_logger=False,
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fronius."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            unique_id, info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(unique_id, raise_on_progress=False)
            self._abort_if_unique_id_configured(
                updates=dict(info), reload_on_update=False
            )
            title = (
                f"SolarNet {'Datalogger' if info['is_logger'] else 'Inverter'}"
                f" at {info['host']}"
            )
            return self.async_create_entry(title=title, data=info)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, conf: dict) -> FlowResult:
        """Import a configuration from config.yaml."""
        return await self.async_step_user(user_input={CONF_HOST: conf[CONF_RESOURCE]})


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
