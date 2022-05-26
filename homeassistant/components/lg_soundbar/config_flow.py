"""Config flow to configure the LG Soundbar integration."""
from queue import Queue
import socket

import temescal
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

DATA_SCHEMA = {
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
}


def test_connect(host, port):
    """LG Soundbar config flow test_connect."""
    uuid_q = Queue(maxsize=1)
    name_q = Queue(maxsize=1)

    def msg_callback(response):
        if response["msg"] == "MAC_INFO_DEV" and "s_uuid" in response["data"]:
            uuid_q.put_nowait(response["data"]["s_uuid"])
        if (
            response["msg"] == "SPK_LIST_VIEW_INFO"
            and "s_user_name" in response["data"]
        ):
            name_q.put_nowait(response["data"]["s_user_name"])

    try:
        connection = temescal.temescal(host, port=port, callback=msg_callback)
        connection.get_mac_info()
        connection.get_info()
        details = {"name": name_q.get(timeout=10), "uuid": uuid_q.get(timeout=10)}
        return details
    except socket.gaierror as err:
        raise ConnectionError(f"Cannot resolve hostname: {host}") from err
    except socket.timeout as err:
        raise ConnectionError(f"Connection timeout with server: {host}:{port}") from err


class LGSoundbarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """LG Soundbar config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is None:
            return await self._show_form(user_input)
        if not errors:
            try:
                details = test_connect(user_input[CONF_HOST], user_input[CONF_PORT])
            except ConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(details["uuid"])
                self._abort_if_unique_id_configured()
                info = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
                return self.async_create_entry(title=details["name"], data=info)

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(DATA_SCHEMA),
                errors=errors,
            )

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(DATA_SCHEMA),
            errors=errors if errors else {},
        )
