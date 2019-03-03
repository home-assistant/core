"""Integrates Native Apps to Home Assistant."""
from homeassistant.helpers.typing import (ConfigType,
                                          HomeAssistantType)

from .const import (ATTR_DELETED_IDS, ATTR_REGISTRATIONS, ATTR_STORE,
                    DOMAIN, STORAGE_KEY, STORAGE_VERSION)

from .http_api import register_http_handlers
from .webhook import register_device_webhook
from .websocket_api import register_websocket_handlers

DEPENDENCIES = ['device_tracker', 'http', 'webhook', 'websocket_api']

REQUIREMENTS = ['PyNaCl==1.3.0']


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the mobile app component."""
    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    app_config = await store.async_load()
    if app_config is None:
        app_config = {ATTR_DELETED_IDS: [], ATTR_REGISTRATIONS: {}}

    if hass.data.get(DOMAIN) is None:
        hass.data[DOMAIN] = {ATTR_DELETED_IDS: [], ATTR_REGISTRATIONS: {}}

    hass.data[DOMAIN][ATTR_DELETED_IDS] = app_config[ATTR_DELETED_IDS]
    hass.data[DOMAIN][ATTR_REGISTRATIONS] = app_config[ATTR_REGISTRATIONS]
    hass.data[DOMAIN][ATTR_STORE] = store

    for device in app_config[ATTR_REGISTRATIONS].values():
        register_device_webhook(hass, store, device)

    register_http_handlers(hass, store)
    register_websocket_handlers(hass)

    return True
