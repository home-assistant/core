"""Config flow for Lutron Caseta."""

from homeassistant import config_entries

from . import DOMAIN


class LutronCasetaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hue config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, import_info):
        """Import a new Caseta bridge as a config entry.

        This flow is triggered by `async_setup`.
        """

        # Abort if existing entry with matching host exists.
        host = import_info["host"]
        if any(host == entry.data["host"] for entry in self._async_current_entries()):
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(title="Caseta Bridge", data={"host": host})
