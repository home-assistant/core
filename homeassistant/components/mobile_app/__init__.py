"""Integrates Native Apps to Home Assistant."""
from contextlib import suppress

from homeassistant.components import cloud, notify as hass_notify
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, discovery
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import (
    ATTR_DEVICE_NAME,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_OS_VERSION,
    CONF_CLOUDHOOK_URL,
    DATA_CONFIG_ENTRIES,
    DATA_DELETED_IDS,
    DATA_DEVICES,
    DATA_PUSH_CHANNEL,
    DATA_STORE,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .helpers import savable_state
from .http_api import RegistrationsView
from .webhook import handle_webhook

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the mobile app component."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    if (app_config := await store.async_load()) is None or not isinstance(
        app_config, dict
    ):
        app_config = {
            DATA_CONFIG_ENTRIES: {},
            DATA_DELETED_IDS: [],
        }

    hass.data[DOMAIN] = {
        DATA_CONFIG_ENTRIES: {},
        DATA_DELETED_IDS: app_config.get(DATA_DELETED_IDS, []),
        DATA_DEVICES: {},
        DATA_PUSH_CHANNEL: {},
        DATA_STORE: store,
    }

    hass.http.register_view(RegistrationsView())

    for deleted_id in hass.data[DOMAIN][DATA_DELETED_IDS]:
        with suppress(ValueError):
            webhook_register(
                hass, DOMAIN, "Deleted Webhook", deleted_id, handle_webhook
            )

    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.NOTIFY, DOMAIN, {}, config)
    )

    websocket_api.async_setup_commands(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a mobile_app entry."""
    registration = entry.data

    webhook_id = registration[CONF_WEBHOOK_ID]

    hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id] = entry

    device_registry = dr.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, registration[ATTR_DEVICE_ID])},
        manufacturer=registration[ATTR_MANUFACTURER],
        model=registration[ATTR_MODEL],
        name=registration[ATTR_DEVICE_NAME],
        sw_version=registration[ATTR_OS_VERSION],
    )

    hass.data[DOMAIN][DATA_DEVICES][webhook_id] = device

    registration_name = f"Mobile App: {registration[ATTR_DEVICE_NAME]}"
    webhook_register(hass, DOMAIN, registration_name, webhook_id, handle_webhook)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    await hass_notify.async_reload(hass, DOMAIN)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a mobile app entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    webhook_id = entry.data[CONF_WEBHOOK_ID]

    webhook_unregister(hass, webhook_id)
    del hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]
    del hass.data[DOMAIN][DATA_DEVICES][webhook_id]
    await hass_notify.async_reload(hass, DOMAIN)

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Cleanup when entry is removed."""
    hass.data[DOMAIN][DATA_DELETED_IDS].append(entry.data[CONF_WEBHOOK_ID])
    store = hass.data[DOMAIN][DATA_STORE]
    await store.async_save(savable_state(hass))

    if CONF_CLOUDHOOK_URL in entry.data:
        with suppress(cloud.CloudNotAvailable):
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
