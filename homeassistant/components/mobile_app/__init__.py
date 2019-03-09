"""Integrates Native Apps to Home Assistant."""
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (DATA_DELETED_IDS, DATA_REGISTRATIONS, DATA_STORE, DOMAIN,
                    STORAGE_KEY, STORAGE_VERSION)

from .http_api import register_http_handlers
from .webhook import register_deleted_webhooks, setup_registration
from .websocket_api import register_websocket_handlers

DEPENDENCIES = ['device_tracker', 'http', 'webhook']

REQUIREMENTS = ['PyNaCl==1.3.0']


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the mobile app component."""
    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    app_config = await store.async_load()
    if app_config is None:
        app_config = {DATA_DELETED_IDS: [], DATA_REGISTRATIONS: {}}

    if hass.data.get(DOMAIN) is None:
        hass.data[DOMAIN] = {DATA_DELETED_IDS: [], DATA_REGISTRATIONS: {}}

    hass.data[DOMAIN][DATA_DELETED_IDS] = app_config[DATA_DELETED_IDS]
    hass.data[DOMAIN][DATA_REGISTRATIONS] = app_config[DATA_REGISTRATIONS]
    hass.data[DOMAIN][DATA_STORE] = store

    for registration in app_config[DATA_REGISTRATIONS].values():
        setup_registration(hass, store, registration)

    register_http_handlers(hass, store)
    register_websocket_handlers(hass)
    register_deleted_webhooks(hass, store)

    return True
