import logging

from aiohttp import ClientError, ClientTimeout, ServerTimeoutError, request
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.core import callback

from .const import DOMAIN

ADVANTAGE_AIR_SCHEMA = vol.Schema(
    {vol.Required(CONF_URL, default="http://192.168.0.10:2025"): str}
)

_LOGGER = logging.getLogger(__name__)


class MyAirConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, info):
        if not info:
            return self._show_form()

        url = info.get(CONF_URL)

        try:
            async with request(
                "GET", f"{url}/getSystemData", timeout=ClientTimeout(total=5)
            ) as resp:
                assert resp.status == 200
                data = await resp.json(content_type=None)
        except ServerTimeoutError as err:
            _LOGGER.error(f"Connection timed out: {err}")
            return self._show_form({"base": "timeout_error"})
        except ClientError as err:
            _LOGGER.error(f"Unable to connect to MyAir: {err}")
            return self._show_form({"base": "connection_error"})

        if "aircons" not in data:
            return self._show_form({"base": "data_error"})

        return self.async_create_entry(
            title=data["system"]["name"],
            data=info,
        )

    @callback
    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=ADVANTAGE_AIR_SCHEMA,
            errors=errors if errors else {},
        )


#    async def async_step_import(self, import_config):
#        """Import a config entry from configuration.yaml."""
#        return await self.async_step_user(import_config)
