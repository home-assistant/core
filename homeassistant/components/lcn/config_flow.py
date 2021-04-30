"""Config flow to configure the LCN integration."""
import logging

import pypck

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from .const import CONF_DIM_MODE, CONF_SK_NUM_TRIES, DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_config_entry(hass, data):
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


async def validate_connection(host_name, data):
    """Validate if a connection to LCN can be established."""
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

    _LOGGER.debug("Validating connection parameters to PCHK host '%s'", host_name)

    connection = pypck.connection.PchkConnectionManager(
        host, port, username, password, settings=settings
    )

    await connection.async_connect(timeout=5)

    _LOGGER.debug("LCN connection validated")
    await connection.async_close()
    return data


@config_entries.HANDLERS.register(DOMAIN)
class LcnFlowHandler(config_entries.ConfigFlow):
    """Handle a LCN config flow."""

    VERSION = 1

    async def async_step_import(self, data):
        """Import existing configuration from LCN."""
        host_name = data[CONF_HOST]
        # validate the imported connection parameters
        try:
            await validate_connection(host_name, data)
        except pypck.connection.PchkAuthenticationError:
            _LOGGER.warning('Authentication on PCHK "%s" failed', host_name)
            return self.async_abort(reason="authentication_error")
        except pypck.connection.PchkLicenseError:
            _LOGGER.warning(
                'Maximum number of connections on PCHK "%s" was '
                "reached. An additional license key is required",
                host_name,
            )
            return self.async_abort(reason="license_error")
        except TimeoutError:
            _LOGGER.warning('Connection to PCHK "%s" failed', host_name)
            return self.async_abort(reason="connection_timeout")

        # check if we already have a host with the same address configured
        entry = get_config_entry(self.hass, data)
        if entry:
            entry.source = config_entries.SOURCE_IMPORT
            self.hass.config_entries.async_update_entry(entry, data=data)
            return self.async_abort(reason="existing_configuration_updated")

        return self.async_create_entry(
            title=f"{host_name}",
            data=data,
        )
