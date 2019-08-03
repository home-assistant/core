"""Config flow for Unifi."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from .const import CONF_CONTROLLER, CONF_SITE_ID, DOMAIN, LOGGER
from .controller import get_controller
from .errors import AlreadyConfigured, AuthenticationRequired, CannotConnect

DEFAULT_PORT = 8443
DEFAULT_SITE_ID = "default"
DEFAULT_VERIFY_SSL = False


@config_entries.HANDLERS.register(DOMAIN)
class UnifiFlowHandler(config_entries.ConfigFlow):
    """Handle a UniFi config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the UniFi flow."""
        self.config = None
        self.desc = None
        self.sites = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            try:
                self.config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_PORT: user_input.get(CONF_PORT),
                    CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
                    CONF_SITE_ID: DEFAULT_SITE_ID,
                }

                controller = await get_controller(self.hass, **self.config)

                self.sites = await controller.sites()

                return await self.async_step_site()

            except AuthenticationRequired:
                errors["base"] = "faulty_credentials"

            except CannotConnect:
                errors["base"] = "service_unavailable"

            except Exception:  # pylint: disable=broad-except
                LOGGER.error(
                    "Unknown error connecting with UniFi Controller at %s",
                    user_input[CONF_HOST],
                )
                return self.async_abort(reason="unknown")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_site(self, user_input=None):
        """Select site to control."""
        errors = {}

        if user_input is not None:
            try:
                desc = user_input.get(CONF_SITE_ID, self.desc)

                for site in self.sites.values():
                    if desc == site["desc"]:
                        self.config[CONF_SITE_ID] = site["name"]
                        break

                for entry in self._async_current_entries():
                    controller = entry.data[CONF_CONTROLLER]
                    if (
                        controller[CONF_HOST] == self.config[CONF_HOST]
                        and controller[CONF_SITE_ID] == self.config[CONF_SITE_ID]
                    ):
                        raise AlreadyConfigured

                data = {CONF_CONTROLLER: self.config}

                return self.async_create_entry(title=desc, data=data)

            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")

        if len(self.sites) == 1:
            self.desc = next(iter(self.sites.values()))["desc"]
            return await self.async_step_site(user_input={})

        if self.desc is not None:
            for site in self.sites.values():
                if self.desc == site["name"]:
                    self.desc = site["desc"]
                    return await self.async_step_site(user_input={})

        sites = []
        for site in self.sites.values():
            sites.append(site["desc"])

        return self.async_show_form(
            step_id="site",
            data_schema=vol.Schema({vol.Required(CONF_SITE_ID): vol.In(sites)}),
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Import from UniFi device tracker config."""
        config = {
            CONF_HOST: import_config[CONF_HOST],
            CONF_USERNAME: import_config[CONF_USERNAME],
            CONF_PASSWORD: import_config[CONF_PASSWORD],
            CONF_PORT: import_config.get(CONF_PORT),
            CONF_VERIFY_SSL: import_config.get(CONF_VERIFY_SSL),
        }

        self.desc = import_config[CONF_SITE_ID]

        return await self.async_step_user(user_input=config)
