"""Config flow for Mikrotik."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback

from .const import (
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_FORCE_DHCP,
    CONF_HUBS,
    CONF_NUM_HUBS,
    DEFAULT_API_PORT,
    DEFAULT_DETECTION_TIME,
    DEFAULT_NAME,
    DOMAIN,
    MAX_NUM_HUBS,
)
from .errors import CannotConnect, LoginError
from .hub import get_api


class MikrotikFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Mikrotik config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MikrotikOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initiate Mikrotik Flow."""
        self.num_hubs = 1
        self.config = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.num_hubs = user_input[CONF_NUM_HUBS]
            self.config[CONF_NAME] = user_input[CONF_NAME]
            self.config[CONF_HUBS] = {}
            return await self.async_step_hub()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_NUM_HUBS, default=1): vol.In([1, 2, 3]),
                }
            ),
        )

    async def async_step_hub(self, user_input=None):
        """Set up a new Mikrotik hub."""
        errors = {}
        if user_input is not None:
            if await self.check_hub_exists(user_input[CONF_HOST]):
                return self.async_abort(reason="already_configured")

            if user_input[CONF_HOST] not in self.config[CONF_HUBS]:
                errors = await self.test_connecting_to_hub(user_input)
            else:
                errors[CONF_HOST] = "hub_exists"

            if not errors:
                self.config[CONF_HUBS][user_input[CONF_HOST]] = user_input
                if len(self.config[CONF_HUBS]) < self.num_hubs:
                    return await self.async_step_hub()

                return self.async_create_entry(
                    title=self.config[CONF_NAME], data=self.config
                )

        return self.async_show_form(
            step_id="hub",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_API_PORT): int,
                    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            description_placeholders={"index": len(self.config[CONF_HUBS]) + 1},
            errors=errors,
        )

    async def check_hub_exists(self, host):
        """Check if hub is already configured."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if host in entry.data[CONF_HUBS]:
                return True
        return False

    async def test_connecting_to_hub(self, entry):
        """Return errors if connection to hub fails."""
        errors = {}
        try:
            await self.hass.async_add_executor_job(get_api, self.hass, entry)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except LoginError:
            errors[CONF_USERNAME] = "wrong_credentials"
            errors[CONF_PASSWORD] = "wrong_credentials"
        return errors

    async def async_step_import(self, import_config):
        """Import Miktortik from config."""
        hubs = import_config.pop(CONF_HUBS)

        if len(hubs) > MAX_NUM_HUBS:
            return self.async_abort(reason="config_error")

        for entry in hubs:
            if await self.check_hub_exists(entry[CONF_HOST]):
                return self.async_abort(reason="already_configured")

        import_config[CONF_HUBS] = {}
        for entry in hubs:
            if entry[CONF_HOST] not in import_config[
                CONF_HUBS
            ] and not await self.test_connecting_to_hub(entry):
                return self.async_abort(reason="conn_error")

            import_config[CONF_HUBS][entry[CONF_HOST]] = entry

        import_config[CONF_DETECTION_TIME] = import_config[CONF_DETECTION_TIME].seconds
        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )


class MikrotikOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Mikrotik options."""

    def __init__(self, config_entry):
        """Initialize Mikrotik options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Mikrotik options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_FORCE_DHCP,
                default=self.config_entry.options.get(CONF_FORCE_DHCP, False),
            ): bool,
            vol.Optional(
                CONF_ARP_PING,
                default=self.config_entry.options.get(CONF_ARP_PING, False),
            ): bool,
            vol.Optional(
                CONF_DETECTION_TIME,
                default=self.config_entry.options.get(
                    CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
                ),
            ): int,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
