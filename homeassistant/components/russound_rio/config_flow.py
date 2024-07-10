"""Config flow to configure russound_rio component."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiorussound import Russound
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, RUSSOUND_RIO_EXCEPTIONS, NoPrimaryControllerException

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=9621): cv.port,
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


def find_primary_controller_metadata(controllers):
    """Find the mac address of the primary Russound controller."""
    for controller_id, mac_address, controller_type in controllers:
        # The integration only cares about the primary controller linked by IP and not any downstream controllers
        if controller_id == 1:
            return (mac_address, controller_type)
    return None


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Russound RIO configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]
            port = user_input[CONF_PORT]

            try:
                russ = Russound(self.hass.loop, host, port)
                async with asyncio.timeout(5):
                    await russ.connect()
                    controllers = await russ.enumerate_controllers()
                    metadata = find_primary_controller_metadata(controllers)
                    if metadata:
                        await self.async_set_unique_id(metadata[0])
                    else:
                        raise NoPrimaryControllerException
                    await russ.close()
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: host, CONF_PORT: port}
                    )
            except RUSSOUND_RIO_EXCEPTIONS as err:
                _LOGGER.error("Could not connect to Russound RIO: %s", err)
                errors["base"] = "cannot_connect"
            except NoPrimaryControllerException as err:
                _LOGGER.error(
                    "Russound RIO device doesn't have a primary controller: %s", err
                )
                errors["base"] = "no_primary_controller"
            else:
                data = {
                    CONF_HOST: host,
                    CONF_NAME: name,
                    CONF_PORT: port,
                }

                return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Attempt to import the existing configuration."""
        self._async_abort_entries_match({CONF_HOST: import_config[CONF_HOST]})
        host = import_config[CONF_HOST]
        name = import_config[CONF_NAME]
        port = import_config.get(CONF_PORT, 9621)

        # Connection logic is repeated here since this method will be removed in future releases
        try:
            russ = Russound(self.hass.loop, host, port)
            async with asyncio.timeout(5):
                await russ.connect()
                controllers = await russ.enumerate_controllers()
                metadata = find_primary_controller_metadata(controllers)
                if metadata:
                    await self.async_set_unique_id(metadata[0])
                else:
                    return self.async_abort(
                        reason="no_primary_controller", description_placeholders={}
                    )
                await russ.close()
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )
        except RUSSOUND_RIO_EXCEPTIONS as err:
            _LOGGER.error("Could not connect to Russound RIO: %s", err)
            return self.async_abort(
                reason="cannot_connect", description_placeholders={}
            )
        else:
            data = {
                CONF_HOST: host,
                CONF_NAME: name,
                CONF_PORT: port,
            }

            return self.async_create_entry(title=name, data=data)
