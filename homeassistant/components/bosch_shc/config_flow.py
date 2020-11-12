"""Config flow for Bosch Smart Home Controller integration."""
import logging

from boschshcpy import SHCSession
from boschshcpy.exceptions import (
    SHCAuthenticationError,
    SHCConnectionError,
    SHCmDNSError,
)
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.zeroconf import async_get_instance
from homeassistant.const import CONF_HOST

from .const import CONF_SSL_CERTIFICATE, CONF_SSL_KEY
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

HOST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def validate_input(hass: core.HomeAssistant, host, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    zeroconf = await async_get_instance(hass)

    session: SHCSession
    session = await hass.async_add_executor_job(
        SHCSession,
        host,
        data[CONF_SSL_CERTIFICATE],
        data[CONF_SSL_KEY],
        True,
        zeroconf,
    )

    await hass.async_add_executor_job(session.authenticate)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch SHC."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    info = None
    host = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                self.info = info = await self._get_info(host)
            except SHCConnectionError:
                errors["base"] = "cannot_connect"
            except SHCmDNSError:
                _LOGGER.warning("Error looking up mDNS entry")
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["mac"])
                self._abort_if_unique_id_configured({CONF_HOST: host})
                self.host = host
                return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user", data_schema=HOST_SCHEMA, errors=errors
        )

    async def async_step_credentials(self, user_input=None):
        """Handle the credentials step."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, self.host, user_input)
            except SHCAuthenticationError:
                errors["base"] = "invalid_auth"
            except SHCConnectionError:
                errors["base"] = "cannot_connect"
            except SHCmDNSError:
                _LOGGER.warning("Error looking up mDNS entry")
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=self.info["title"],
                    data={**user_input, CONF_HOST: self.host},
                )
        else:
            user_input = {}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SSL_CERTIFICATE, default=user_input.get(CONF_SSL_CERTIFICATE)
                ): str,
                vol.Required(CONF_SSL_KEY, default=user_input.get(CONF_SSL_KEY)): str,
            }
        )

        return self.async_show_form(
            step_id="credentials", data_schema=schema, errors=errors
        )

    async def async_step_zeroconf(self, zeroconf_info):
        """Handle zeroconf discovery."""
        if not zeroconf_info.get("name", "").startswith("Bosch SHC"):
            return self.async_abort(reason="not_bosch_shc")

        try:
            self.info = info = await self._get_info(zeroconf_info["host"])
        except SHCConnectionError:
            return self.async_abort(reason="cannot_connect")
        except SHCmDNSError:
            _LOGGER.exception("Error looking up mDNS entry")
            return self.async_abort(reason="cannot_connect")

        local_name = zeroconf_info["hostname"][:-1]
        node_name = local_name[: -len(".local")]

        await self.async_set_unique_id(info["mac"])
        self._abort_if_unique_id_configured({CONF_HOST: zeroconf_info["host"]})
        self.host = zeroconf_info["host"]
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {"name": node_name}
        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(self, user_input=None):
        """Handle discovery confirm."""
        errors = {}
        if user_input is not None:
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "model": "Bosch SHC",
                "host": self.host,
            },
            errors=errors,
        )

    async def _get_info(self, host):
        """Get additional information."""
        zeroconf = await async_get_instance(self.hass)

        session = await self.hass.async_add_executor_job(
            SHCSession,
            host,
            "",
            "",
            True,
            zeroconf,
        )

        information = await self.hass.async_add_executor_job(session.mdns_info)
        return {"title": information.name, "mac": information.mac_address}
