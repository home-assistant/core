"""Integrates Native Apps to Home Assistant."""
from homeassistant import config_entries
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (ATTR_DEVICE_NAME, DATA_DELETED_IDS, DATA_STORE, DOMAIN,
                    STORAGE_KEY, STORAGE_VERSION)

from .http_api import RegistrationsView
from .webhook import register_deleted_webhooks, setup_registration
from .websocket_api import register_websocket_handlers

DEPENDENCIES = ['device_tracker', 'http', 'webhook']

REQUIREMENTS = ['PyNaCl==1.3.0']


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the mobile app component."""
    hass.data[DOMAIN] = {DATA_DELETED_IDS: []}
    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    app_config = await store.async_load()
    if app_config is None:
        app_config = {DATA_DELETED_IDS: []}

    hass.data[DOMAIN] = {
        DATA_DELETED_IDS: app_config.get(DATA_DELETED_IDS, []),
        DATA_STORE: store
    }

    hass.http.register_view(RegistrationsView())
    register_websocket_handlers(hass)
    register_deleted_webhooks(hass)

    return True


async def async_setup_entry(hass, entry):
    """Set up a mobile_app entry."""
    return await setup_registration(hass, entry)


@config_entries.HANDLERS.register(DOMAIN)
class MobileAppFlowHandler(config_entries.ConfigFlow):
    """Handle a Mobile App config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return self.async_abort(reason='install_app')

    async def async_step_registration(self, user_input=None):
        """Handle a flow initialized during registration."""
        return self.async_create_entry(title=user_input[ATTR_DEVICE_NAME],
                                       data=user_input)
