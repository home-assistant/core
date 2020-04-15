"""Config flow for Plaato."""
from pyplaato.plaato import PlaatoDeviceType
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN, CONF_WEBHOOK_ID

from .const import (
    CONF_CLOUDHOOK,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_USE_WEBHOOK,
    DOCS_URL,
    DOMAIN,
    PLACEHOLDER_DOCS_URL,
    PLACEHOLDER_WEBHOOK_URL,
)


class PlaatoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles a Plaato config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._init_info = None
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle user step."""
        # if self._async_current_entries():
        #     return self.async_abort(reason="one_instance_allowed")

        if user_input is not None:
            use_webhook = user_input.get(CONF_USE_WEBHOOK, False)
            auth_token = user_input.get(CONF_TOKEN, None)

            if use_webhook is False and auth_token is None:
                self._init_info = user_input
                return await self.async_step_device_type()

            user_input[CONF_WEBHOOK_ID] = None
            user_input[CONF_DEVICE_TYPE] = self._init_info.get(CONF_DEVICE_TYPE, None)
            user_input[CONF_DEVICE_NAME] = self._init_info.get(CONF_DEVICE_NAME, None)

            description_placeholders = {
                PLACEHOLDER_WEBHOOK_URL: "Not available",
                PLACEHOLDER_DOCS_URL: DOCS_URL,
            }

            if user_input[CONF_DEVICE_TYPE] is None:
                return self.async_abort(reason="no_device")

            device_type = PlaatoDeviceType(user_input[CONF_DEVICE_TYPE])
            if device_type is PlaatoDeviceType.Airlock and user_input[CONF_USE_WEBHOOK]:
                webhook_id, webhook_url, cloudhook = await self._get_webhook_id()
                user_input[CONF_WEBHOOK_ID] = webhook_id
                user_input[CONF_CLOUDHOOK] = cloudhook
                description_placeholders[PLACEHOLDER_WEBHOOK_URL] = webhook_url
            else:
                await self.async_set_unique_id(auth_token)
                self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=device_type.name,
                data=user_input,
                description_placeholders=description_placeholders,
            )

        return await self._show_config_form(user_input)

    async def async_step_device_type(self, user_input=None):
        """Handle device type step."""
        device_type = PlaatoDeviceType(self._init_info[CONF_DEVICE_TYPE])
        data_scheme = vol.Schema({vol.Optional(CONF_TOKEN, default=None): str})
        if device_type is PlaatoDeviceType.Airlock:
            data_scheme = data_scheme.extend(
                {vol.Optional(CONF_USE_WEBHOOK, default=False): bool}
            )

        return self.async_show_form(
            step_id="user", data_schema=data_scheme, errors=self._errors,
        )

    async def _show_config_form(self, user_input):
        """Show the configuration form."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_NAME, default=None): str,
                    vol.Required(CONF_DEVICE_TYPE, default=None): vol.In(
                        list(PlaatoDeviceType)
                    ),
                }
            ),
            errors=self._errors,
        )

    async def _get_webhook_id(self):
        """Generate webhook ID."""
        webhook_id = self.hass.components.webhook.async_generate_id()
        if self.hass.components.cloud.async_active_subscription():
            webhook_url = await self.hass.components.cloud.async_create_cloudhook(
                webhook_id
            )
            cloudhook = True
        else:
            webhook_url = self.hass.components.webhook.async_generate_url(webhook_id)
            cloudhook = False

        return webhook_id, webhook_url, cloudhook
