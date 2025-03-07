"""Config flow to configure the LCN integration."""

from __future__ import annotations

import logging
from typing import Any

import pypck
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_BASE,
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import PchkConnectionManager
from .const import CONF_ACKNOWLEDGE, CONF_DIM_MODE, CONF_SK_NUM_TRIES, DIM_MODES, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_DATA = {
    vol.Required(CONF_IP_ADDRESS, default=""): str,
    vol.Required(CONF_PORT, default=4114): cv.positive_int,
    vol.Required(CONF_USERNAME, default=""): str,
    vol.Required(CONF_PASSWORD, default=""): str,
    vol.Required(CONF_SK_NUM_TRIES, default=0): cv.positive_int,
    vol.Required(CONF_DIM_MODE, default="STEPS200"): vol.In(DIM_MODES),
    vol.Required(CONF_ACKNOWLEDGE, default=False): cv.boolean,
}

USER_DATA = {vol.Required(CONF_HOST, default="pchk"): str, **CONFIG_DATA}

CONFIG_SCHEMA = vol.Schema(CONFIG_DATA)
USER_SCHEMA = vol.Schema(USER_DATA)


def get_config_entry(
    hass: HomeAssistant, data: ConfigType
) -> config_entries.ConfigEntry | None:
    """Check config entries for already configured entries based on the ip address/port."""
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data[CONF_IP_ADDRESS] == data[CONF_IP_ADDRESS]
            and entry.data[CONF_PORT] == data[CONF_PORT]
        ),
        None,
    )


async def validate_connection(data: ConfigType) -> str | None:
    """Validate if a connection to LCN can be established."""
    error = None
    host_name = data[CONF_HOST]
    host = data[CONF_IP_ADDRESS]
    port = data[CONF_PORT]
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    sk_num_tries = data[CONF_SK_NUM_TRIES]
    dim_mode = data[CONF_DIM_MODE]
    acknowledge = data[CONF_ACKNOWLEDGE]

    settings = {
        "SK_NUM_TRIES": sk_num_tries,
        "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[dim_mode],
        "ACKNOWLEDGE": acknowledge,
    }

    _LOGGER.debug("Validating connection parameters to PCHK host '%s'", host_name)

    connection = PchkConnectionManager(
        host, port, username, password, settings=settings
    )

    try:
        await connection.async_connect(timeout=5)
        _LOGGER.debug("LCN connection validated")
    except pypck.connection.PchkAuthenticationError:
        _LOGGER.warning('Authentication on PCHK "%s" failed', host_name)
        error = "authentication_error"
    except pypck.connection.PchkLicenseError:
        _LOGGER.warning(
            'Maximum number of connections on PCHK "%s" was '
            "reached. An additional license key is required",
            host_name,
        )
        error = "license_error"
    except (
        pypck.connection.PchkConnectionFailedError,
        pypck.connection.PchkConnectionRefusedError,
    ):
        _LOGGER.warning('Connection to PCHK "%s" failed', host_name)
        error = "connection_refused"

    await connection.async_close()
    return error


class LcnFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a LCN config flow."""

    VERSION = 3
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

        errors = None
        if get_config_entry(self.hass, user_input):
            errors = {CONF_BASE: "already_configured"}
        elif (error := await validate_connection(user_input)) is not None:
            errors = {CONF_BASE: error}

        if errors is not None:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    USER_SCHEMA, user_input
                ),
                errors=errors,
            )

        data: dict = {
            **user_input,
            CONF_DEVICES: [],
            CONF_ENTITIES: [],
        }

        return self.async_create_entry(title=data[CONF_HOST], data=data)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Reconfigure LCN configuration."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors = None
        if user_input is not None:
            user_input[CONF_HOST] = reconfigure_entry.data[CONF_HOST]

            await self.hass.config_entries.async_unload(reconfigure_entry.entry_id)
            if (error := await validate_connection(user_input)) is not None:
                errors = {CONF_BASE: error}

            if errors is None:
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

            await self.hass.config_entries.async_setup(reconfigure_entry.entry_id)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )
