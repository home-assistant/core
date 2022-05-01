"""Config flow to configure the LG Soundbar integration."""
import temescal
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_UNIQUE_ID

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

DATA_SCHEMA = {
    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    vol.Optional(CONF_NAME): str,
}


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
                uuid = self.test_connect(user_input[CONF_HOST], user_input[CONF_PORT])
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

    _uuid = None

    def get_uuid(self, response):
        """LG Soundbar get uuid."""
        data = response["data"]
        # we use the s_uuid not the MAC as s_bt_mac can responed with '00:00:00:00:00:00'
        if response["msg"] == "MAC_INFO_DEV":
            if "s_uuid" in data:
                self._uuid = data["s_uuid"]

    def test_connect(self, host, port):
        """LG Soundbar config flow test_connect."""
        try:
            temescal.temescal(host, port=port, callback=self.get_uuid).get_mac_info()
            while True:
                if self._uuid:
                    break
            return self._uuid
        except Exception as err:
            raise ConnectionError("Connection failed.") from err
