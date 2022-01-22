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
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_DIM_MODE, CONF_SK_NUM_TRIES, DIM_MODES, DOMAIN
from .helpers import purge_device_registry, purge_entity_registry

_LOGGER = logging.getLogger(__name__)


def get_config_entry(
    hass: HomeAssistant, host_name: str
) -> config_entries.ConfigEntry | None:
    """Check config entries for already configured entries based on the ip address/port."""
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.title == host_name
        ),
        None,
    )


async def validate_connection(host_name: str, data: dict[str, Any]) -> str | None:
    """Validate if a connection to LCN can be established."""
    _LOGGER.debug("Validating connection parameters to PCHK host '%s'", host_name)

    error = None
    host = data[CONF_IP_ADDRESS]
    port = data[CONF_PORT]
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    sk_num_tries = data[CONF_SK_NUM_TRIES]
    dim_mode = data[CONF_DIM_MODE]
    settings = {
        "SK_NUM_TRIES": sk_num_tries,
        "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[dim_mode],
    }

    connection = pypck.connection.PchkConnectionManager(
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
    except (TimeoutError, ConnectionRefusedError):
        _LOGGER.warning('Connection to PCHK "%s" failed', host_name)
        error = "connection_refused"

    await connection.async_close()
    return error


class LcnFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a LCN config flow."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow for this handler."""
        return LcnOptionsFlowHandler(config_entry)

    async def async_step_import(self, config_data: dict[str, Any]) -> FlowResult:
        """Import existing configuration from LCN."""
        host_name = config_data[CONF_HOST]
        data = {key: config_data[key] for key in (CONF_DEVICES, CONF_ENTITIES)}

        if entry := get_config_entry(self.hass, host_name):
            entry.source = config_entries.SOURCE_IMPORT
            # Cleanup entity and device registry, if we imported from configuration.yaml to
            # remove orphans when entities were removed from configuration
            purge_entity_registry(self.hass, entry.entry_id, data)
            purge_device_registry(self.hass, entry.entry_id, data)

            if entry.version == 1:
                self.hass.config_entries.async_update_entry(entry, data=config_data)
            else:
                self.hass.config_entries.async_update_entry(entry, data=data)
            return self.async_abort(reason="existing_configuration_updated")

        # try import connection parameters
        try:
            options = {
                key: config_data[key]
                for key in (
                    CONF_IP_ADDRESS,
                    CONF_PORT,
                    CONF_USERNAME,
                    CONF_PASSWORD,
                    CONF_SK_NUM_TRIES,
                    CONF_DIM_MODE,
                )
            }
        except KeyError:
            # expected connection parameters not defined in configuration.yaml
            _LOGGER.warning('No connection parameters defined for host "%s"', host_name)
            return self.async_abort(reason="import_connection_error")

        # validate the imported connection parameters
        if (error := await validate_connection(host_name, options)) is not None:
            return self.async_abort(reason=error)

        return self.async_create_entry(title=f"{host_name}", data=data, options=options)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="pchk"): str,
                vol.Required(CONF_IP_ADDRESS, default="192.168.2.41"): str,
                vol.Required(CONF_PORT, default=4114): cv.positive_int,
                vol.Required(CONF_USERNAME, default="lcn"): str,
                vol.Required(CONF_PASSWORD, default="lcn"): str,
                vol.Required(CONF_SK_NUM_TRIES, default=0): cv.positive_int,
                vol.Required(CONF_DIM_MODE, default="STEPS200"): vol.In(DIM_MODES),
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        host_name = user_input[CONF_HOST]
        data: dict = {CONF_DEVICES: [], CONF_ENTITIES: []}
        options = {
            key: user_input[key]
            for key in (
                CONF_IP_ADDRESS,
                CONF_PORT,
                CONF_USERNAME,
                CONF_PASSWORD,
                CONF_SK_NUM_TRIES,
                CONF_DIM_MODE,
            )
        }

        errors = None
        if get_config_entry(self.hass, host_name):
            errors = {CONF_HOST: "already_configured"}
        elif (error := await validate_connection(host_name, options)) is not None:
            errors = {CONF_BASE: error}

        if errors is not None:
            return self.async_show_form(
                step_id="user", data_schema=data_schema, errors=errors
            )

        return self.async_create_entry(title=host_name, data=data, options=options)


class LcnOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle LCN options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize LCN options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the LCN options."""
        return await self.async_step_host_options(user_input)

    async def async_step_host_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """For host options."""
        errors = None
        if user_input is not None:
            if (
                error := await validate_connection(self.config_entry.title, user_input)
            ) is None:
                self.options.update(user_input)
                return self.async_create_entry(title="", data=self.options)

            errors = {CONF_BASE: error}

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_IP_ADDRESS, default=self.options[CONF_IP_ADDRESS]
                ): str,
                vol.Required(
                    CONF_PORT, default=self.options[CONF_PORT]
                ): cv.positive_int,
                vol.Required(CONF_USERNAME, default=self.options[CONF_USERNAME]): str,
                vol.Required(CONF_PASSWORD, default=self.options[CONF_PASSWORD]): str,
                vol.Required(
                    CONF_SK_NUM_TRIES, default=self.options[CONF_SK_NUM_TRIES]
                ): cv.positive_int,
                vol.Required(
                    CONF_DIM_MODE, default=self.options[CONF_DIM_MODE]
                ): vol.In(DIM_MODES),
            }
        )
        return self.async_show_form(
            step_id="host_options", data_schema=data_schema, errors=errors or {}
        )
