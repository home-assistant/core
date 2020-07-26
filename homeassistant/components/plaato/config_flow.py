"""Config flow for Plaato."""
import logging

from pyplaato.plaato import PlaatoDeviceType
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN, CONF_WEBHOOK_ID
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from ...config_entries import ConfigEntry
from .const import (
    CONF_CLOUDHOOK,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_UPDATE_INTERVAL,
    CONF_USE_WEBHOOK,
    DOCS_URL,
    PLACEHOLDER_DEVICE_NAME,
    PLACEHOLDER_DEVICE_TYPE,
    PLACEHOLDER_DOCS_URL,
    PLACEHOLDER_WEBHOOK_URL,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__package__)


class PlaatoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles a Plaato config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._init_info = {}
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle user step."""
        return self.async_show_form(
            step_id="device_type",
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

    async def async_step_create_entry(self):
        """Create the entry step."""
        if self._init_info.get(CONF_DEVICE_TYPE, None) is None:
            return self.async_abort(reason="no_device")

        auth_token = self._init_info.get(CONF_TOKEN, None)
        webhook_id = self._init_info.get(CONF_WEBHOOK_ID, None)
        device_name = self._init_info.get(CONF_DEVICE_NAME, None)
        device_type = PlaatoDeviceType(self._init_info.get(CONF_DEVICE_TYPE))

        unique_id = auth_token if auth_token else webhook_id

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=device_type.name,
            data=self._init_info,
            description_placeholders={
                PLACEHOLDER_DEVICE_TYPE: device_type.name,
                PLACEHOLDER_DEVICE_NAME: device_name,
            },
        )

    async def async_step_validate(self, user_input=None):
        """Validate config step."""
        use_webhook = user_input.get(CONF_USE_WEBHOOK, False)
        auth_token = user_input.get(CONF_TOKEN, None)
        device_type = self._init_info[CONF_DEVICE_TYPE]

        self._init_info[CONF_USE_WEBHOOK] = use_webhook
        self._init_info[CONF_TOKEN] = auth_token

        if use_webhook:
            if device_type != PlaatoDeviceType.Airlock:
                self._errors["base"] = "invalid_webhook_device"
                return await self._show_api_method_form(device_type)

            webhook_id, webhook_url, cloudhook = await self._get_webhook_id()
            self._init_info[CONF_WEBHOOK_ID] = webhook_id
            self._init_info[CONF_CLOUDHOOK] = cloudhook

            return self.async_show_form(
                step_id="webhook",
                errors=self._errors,
                description_placeholders={
                    PLACEHOLDER_WEBHOOK_URL: webhook_url,
                    PLACEHOLDER_DOCS_URL: DOCS_URL,
                },
            )

        if not auth_token and not use_webhook:
            self._errors["base"] = "no_api_method"
            return await self._show_api_method_form(device_type)

        if not auth_token:
            self._errors["base"] = "no_auth_token"
            return await self._show_api_method_form(device_type)

        return await self.async_step_create_entry()

    async def async_step_device_type(self, user_input=None):
        """Handle device type step."""
        device_type = PlaatoDeviceType(user_input.get(CONF_DEVICE_TYPE))
        device_name = user_input.get(CONF_DEVICE_NAME)

        self._init_info[CONF_DEVICE_TYPE] = device_type
        self._init_info[CONF_DEVICE_NAME] = device_name

        return await self._show_api_method_form(device_type)

    async def async_step_webhook(self, user_input=None):
        """Handle device type step."""
        return await self.async_step_create_entry()

    async def _show_api_method_form(self, device_type: PlaatoDeviceType):
        data_scheme = vol.Schema(
            {
                vol.Optional(CONF_TOKEN, default=""): str,
                vol.Optional(CONF_USE_WEBHOOK, default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="validate",
            data_schema=data_scheme,
            errors=self._errors,
            description_placeholders={PLACEHOLDER_DEVICE_TYPE: device_type.name},
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PlaatoOptionsFlowHandler(config_entry)


class PlaatoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Plaato options."""

    def __init__(self, config_entry: ConfigEntry):
        """Initialize domain options flow."""
        super().__init__()

        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        use_webhook = self._config_entry.data.get(CONF_USE_WEBHOOK, False)
        if use_webhook:
            return await self.async_step_webhook()

        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=self._config_entry.options.get(CONF_UPDATE_INTERVAL, 5),
                    ): cv.positive_int
                }
            ),
        )

    async def async_step_webhook(self, user_input=None):
        """Manage the options for webhook device."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        webhook_id = self._config_entry.data.get(CONF_WEBHOOK_ID, None)
        webhook_url = (
            ""
            if webhook_id is None
            else self.hass.components.webhook.async_generate_url(webhook_id)
        )

        return self.async_show_form(
            step_id="webhook",
            description_placeholders={PLACEHOLDER_WEBHOOK_URL: webhook_url},
        )
