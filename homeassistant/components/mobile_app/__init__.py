"""Integrates Native Apps to Home Assistant."""
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass

from .const import (ATTR_APP_COMPONENT, DATA_DELETED_IDS, DATA_REGISTRATIONS,
                    DATA_STORE, DOMAIN, STORAGE_KEY, STORAGE_VERSION)

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


@bind_hass
def async_registrations(hass: HomeAssistantType, component: str) -> list:
    """Return all registrations with the given domain set for app_component."""
    registrations = []

    if DOMAIN not in hass.data:
        return registrations

    for registration in hass.data[DOMAIN][DATA_REGISTRATIONS].values():
        if registration.get(ATTR_APP_COMPONENT) == component:
            registrations.append(registration)

    return registrations


@bind_hass
def async_registration_for_webhook_id(hass: HomeAssistantType,
                                      webhook_id: str) -> dict:
    """Return registrations for the given webhook ID."""
    if DOMAIN not in hass.data:
        return None

    return hass.data[DOMAIN][DATA_REGISTRATIONS].get(webhook_id)
