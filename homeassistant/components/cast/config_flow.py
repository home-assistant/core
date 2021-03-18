"""Config flow for Cast."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .const import CONF_KNOWN_HOSTS, DOMAIN

KNOWN_HOSTS_SCHEMA = vol.Schema(vol.All(cv.ensure_list, [cv.string]))


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize flow."""
        self._known_hosts = None

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return CastOptionsFlowHandler(config_entry)

    async def async_step_import(self, import_data=None):
        """Import data."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        data = {CONF_KNOWN_HOSTS: self._known_hosts}
        return self.async_create_entry(title="Google Cast", data=data)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_config()

    async def async_step_zeroconf(self, discovery_info):
        """Handle a flow initialized by zeroconf discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(DOMAIN)

        return await self.async_step_confirm()

    async def async_step_config(self, user_input=None):
        """Confirm the setup."""
        errors = {}
        data = {CONF_KNOWN_HOSTS: self._known_hosts}

        if user_input is not None:
            bad_hosts = False
            known_hosts = user_input[CONF_KNOWN_HOSTS]
            known_hosts = [x.strip() for x in known_hosts.split(",") if x.strip()]
            try:
                known_hosts = KNOWN_HOSTS_SCHEMA(known_hosts)
            except vol.Invalid:
                errors["base"] = "invalid_known_hosts"
                bad_hosts = True
            else:
                data[CONF_KNOWN_HOSTS] = known_hosts
            if not bad_hosts:
                return self.async_create_entry(title="Google Cast", data=data)

        fields = {}
        fields[vol.Optional(CONF_KNOWN_HOSTS, default="")] = str

        return self.async_show_form(
            step_id="config", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_confirm(self, user_input=None):
        """Confirm the setup."""

        data = {CONF_KNOWN_HOSTS: self._known_hosts}

        if user_input is not None:
            return self.async_create_entry(title="Google Cast", data=data)

        return self.async_show_form(step_id="confirm")


class CastOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Google Cast options."""

    def __init__(self, config_entry):
        """Initialize MQTT options flow."""
        self.config_entry = config_entry
        self.broker_config = {}
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the Cast options."""
        return await self.async_step_options()

    async def async_step_options(self, user_input=None):
        """Manage the MQTT options."""
        errors = {}
        current_config = self.config_entry.data
        if user_input is not None:
            bad_hosts = False

            known_hosts = user_input.get(CONF_KNOWN_HOSTS, "")
            known_hosts = [x.strip() for x in known_hosts.split(",") if x.strip()]
            try:
                known_hosts = KNOWN_HOSTS_SCHEMA(known_hosts)
            except vol.Invalid:
                errors["base"] = "invalid_known_hosts"
                bad_hosts = True
            if not bad_hosts:
                updated_config = {}
                updated_config[CONF_KNOWN_HOSTS] = known_hosts
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=updated_config
                )
                return self.async_create_entry(title="", data=None)

        fields = {}
        known_hosts_string = ""
        if current_config.get(CONF_KNOWN_HOSTS):
            known_hosts_string = ",".join(current_config.get(CONF_KNOWN_HOSTS))
        fields[
            vol.Optional(
                "known_hosts", description={"suggested_value": known_hosts_string}
            )
        ] = str

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema(fields),
            errors=errors,
        )
