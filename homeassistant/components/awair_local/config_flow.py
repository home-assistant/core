"""Config flow for Awair."""

from typing import Optional

from python_awair import AwairLocal
from python_awair.exceptions import AwairError
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOSTS
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER  # pylint: disable=unused-import


class AwairFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Awair."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, conf: dict):
        """Import a configuration from config.yaml."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        _, error = await self._check_connection(conf[CONF_HOSTS])
        if error is not None:
            return self.async_abort(reason=error)

        return self.async_create_entry(
            title="Awair Local Sensors",
            data={CONF_HOSTS: conf[CONF_HOSTS]},
        )

    async def async_step_user(self, user_input: Optional[dict] = None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            user, error = await self._check_connection(user_input[CONF_HOSTS])

            if user is not None:
                await self.async_set_unique_id(user.email)
                self._abort_if_unique_id_configured()

                title = f"{user.email} ({user.user_id})"
                return self.async_create_entry(title=title, data=user_input)

            if error != "auth":
                return self.async_abort(reason=error)

            errors = {CONF_HOSTS: "auth"}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOSTS): str}),
            errors=errors,
        )

    async def _check_connection(self, device_addrs_str: str):
        """Check the access token is valid."""
        device_addrs = [addr.strip() for addr in device_addrs_str.split(",")]
        session = async_get_clientsession(self.hass)
        awair = AwairLocal(session=session, device_addrs=device_addrs)

        try:
            devices = await awair.devices()
            if not devices:
                return (None, "no_devices")

            if len(devices) != len(device_addrs):
                return (None, "not enough devices")

            return (devices[0], None)

        except AwairError as err:
            LOGGER.error("Unexpected API error: %s", err)
            return (None, "unknown")
