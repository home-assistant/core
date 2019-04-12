"""Integrates Native Apps to Home Assistant."""
from homeassistant import config_entries
from homeassistant.components.webhook import async_register as webhook_register
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (ATTR_APP_ID, ATTR_APP_NAME, DATA_BINARY_SENSOR,
                    DATA_CONFIG_ENTRIES, DATA_DELETED_IDS,
                    DATA_LOADED_ENTITIES, DATA_LOADED_REGISTRATIONS,
                    DATA_REGISTRATIONS, DATA_SENSOR, DATA_STORE, DOMAIN,
                    STORAGE_KEY, STORAGE_VERSION)

from .device_helpers import register_device
from .http_api import RegistrationsView
from .webhook import handle_webhook
from .websocket_api import register_websocket_handlers

DEPENDENCIES = ['device_tracker', 'http', 'webhook']

REQUIREMENTS = ['PyNaCl==1.3.0']


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the mobile app component."""
    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    app_config = await store.async_load()
    if app_config is None:
        app_config = {
            DATA_BINARY_SENSOR: {},
            DATA_CONFIG_ENTRIES: {},
            DATA_DELETED_IDS: [],
            DATA_LOADED_ENTITIES: [],
            DATA_LOADED_REGISTRATIONS: [],
            DATA_REGISTRATIONS: {},
            DATA_SENSOR: {}
        }

    hass.data[DOMAIN] = {
        DATA_BINARY_SENSOR: app_config.get(DATA_BINARY_SENSOR, {}),
        DATA_CONFIG_ENTRIES: {},
        DATA_DELETED_IDS: app_config.get(DATA_DELETED_IDS, []),
        DATA_LOADED_ENTITIES: [],
        DATA_LOADED_REGISTRATIONS: [],
        DATA_REGISTRATIONS: app_config.get(DATA_REGISTRATIONS, {}),
        DATA_SENSOR: app_config.get(DATA_SENSOR, {}),
        DATA_STORE: store,
    }

    hass.http.register_view(RegistrationsView())
    register_websocket_handlers(hass)

    for deleted_id in hass.data[DOMAIN][DATA_DELETED_IDS]:
        try:
            webhook_register(hass, DOMAIN, "Deleted Webhook", deleted_id,
                             handle_webhook)
        except ValueError:
            pass

    hass.async_create_task(async_load_platform(
        hass, 'notify', DOMAIN, {}, config))

    return True


async def async_setup_entry(hass, entry):
    """Set up a mobile_app entry."""
    app_id = entry.data[ATTR_APP_ID]

    hass.data[DOMAIN][DATA_CONFIG_ENTRIES][app_id] = entry

    for registration in hass.data[DOMAIN][DATA_REGISTRATIONS].values():
        await register_device(hass, entry, registration)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry,
                                                      DATA_BINARY_SENSOR))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, DATA_SENSOR))

    return True


@config_entries.HANDLERS.register(DOMAIN)
class MobileAppFlowHandler(config_entries.ConfigFlow):
    """Handle a Mobile App config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        placeholders = {
            'apps_url':
                'https://www.home-assistant.io/components/mobile_app/#apps'
        }

        return self.async_abort(reason='install_app',
                                description_placeholders=placeholders)

    async def async_step_registration(self, user_input=None):
        """Handle a flow initialized during registration."""
        return self.async_create_entry(title=user_input[ATTR_APP_NAME],
                                       data=user_input)
