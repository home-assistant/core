"""Config flow to configure the LG Soundbar integration."""
from queue import Queue

import temescal
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_UNIQUE_ID

from .const import DEFAULT_PORT, DOMAIN

DATA_SCHEMA = {
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    vol.Optional(CONF_NAME): str,
}


def test_connect(host, port):
    """LG Soundbar config flow test_connect."""
    uuid_q = Queue(maxsize=1)

    def msg_callback(response):
        if response["msg"] == "MAC_INFO_DEV" and "s_uuid" in response["data"]:
            uuid_q.put_nowait(response["data"]["s_uuid"])

    try:
        temescal.temescal(host, port=port, callback=msg_callback).get_mac_info()
        return uuid_q.get(timeout=10)
    except Exception as err:
        raise ConnectionError("Connection failed.") from err


class LGSoundbarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """LG Soundbar config flow."""

    VERSION = 1

    async def async_step_details(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is None:
            return await self._show_form(user_input)
        if not errors:
            try:
                uuid = await self.hass.async_add_executor_job(
                    user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except ConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(uuid)
                self._abort_if_unique_id_configured()
                info = {
                    CONF_UNIQUE_ID: uuid,
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_NAME: user_input[CONF_NAME],
                }
                return self.async_create_entry(title=user_input[CONF_NAME], data=info)

            return self.async_show_form(
                step_id="details",
                data_schema=vol.Schema(DATA_SCHEMA),
                errors=errors,
            )

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="details",
            data_schema=vol.Schema(DATA_SCHEMA),
            errors=errors if errors else {},
        )
