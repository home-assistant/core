"""Integrates Native Apps to Home Assistant."""
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass

from .const import (ATTR_APP_COMPONENT, ATTR_APP_DATA, ATTR_DELETED_IDS,
                    ATTR_REGISTRATIONS, ATTR_STORE, DOMAIN, STORAGE_KEY,
                    STORAGE_VERSION)

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


@bind_hass
def async_devices(hass: HomeAssistantType, component: str) -> list:
    """Return all devices with the given domain set for app_component."""
    devices = []

    if DOMAIN not in hass.data:
        return devices

    for device in hass.data[DOMAIN][ATTR_REGISTRATIONS].values():
        if device.get(ATTR_APP_COMPONENT) == component:
            devices.append(device)

    return devices


@bind_hass
def async_devices_with_key(hass: HomeAssistantType, component: str,
                           key: str) -> list:
    """Return devices for the given component that has the key in app_data."""
    devices = []

    if DOMAIN not in hass.data:
        return devices

    for device in hass.data[DOMAIN][ATTR_REGISTRATIONS].values():
        if (ATTR_APP_COMPONENT in device and key in device[ATTR_APP_DATA] and
                device[ATTR_APP_COMPONENT] == component):
            devices.append(device)

    return devices


@bind_hass
def async_device_for_webhook_id(hass: HomeAssistantType,
                                webhook_id: str) -> dict:
    """Return devices for the given webhook ID."""
    if DOMAIN not in hass.data:
        return None

    return hass.data[DOMAIN][ATTR_REGISTRATIONS].get(webhook_id)
