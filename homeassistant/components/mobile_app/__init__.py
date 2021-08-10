"""Integrates Native Apps to Home Assistant."""
from contextlib import suppress

import voluptuous as vol

from homeassistant.components import cloud, notify as hass_notify, websocket_api
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, discovery
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DEVICE_NAME,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_OS_VERSION,
    CONF_CLOUDHOOK_URL,
    CONF_USER_ID,
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

PLATFORMS = "sensor", "binary_sensor", "device_tracker"


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the mobile app component."""
    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    app_config = await store.async_load()
    if app_config is None:
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
        discovery.async_load_platform(hass, "notify", DOMAIN, {}, config)
    )

    websocket_api.async_register_command(hass, handle_push_notification_channel)

    return True


async def async_setup_entry(hass, entry):
    """Set up a mobile_app entry."""
    registration = entry.data

    webhook_id = registration[CONF_WEBHOOK_ID]

    hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id] = entry

    device_registry = await dr.async_get_registry(hass)

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


async def async_unload_entry(hass, entry):
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


async def async_remove_entry(hass, entry):
    """Cleanup when entry is removed."""
    hass.data[DOMAIN][DATA_DELETED_IDS].append(entry.data[CONF_WEBHOOK_ID])
    store = hass.data[DOMAIN][DATA_STORE]
    await store.async_save(savable_state(hass))

    if CONF_CLOUDHOOK_URL in entry.data:
        with suppress(cloud.CloudNotAvailable):
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "mobile_app/push_notification_channel",
        vol.Required("webhook_id"): str,
    }
)
def handle_push_notification_channel(hass, connection, msg):
    """Set up a direct push notification channel."""
    webhook_id = msg["webhook_id"]

    # Validate that the webhook ID is registered to the user of the websocket connection
    config_entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES].get(webhook_id)

    if config_entry is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Webhook ID not found"
        )
        return

    if config_entry.data[CONF_USER_ID] != connection.user.id:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_UNAUTHORIZED,
            "User not linked to this webhook ID",
        )
        return

    registered_channels = hass.data[DOMAIN][DATA_PUSH_CHANNEL]

    if webhook_id in registered_channels:
        registered_channels.pop(webhook_id)

    @callback
    def forward_push_notification(data):
        """Forward events to websocket."""
        connection.send_message(websocket_api.messages.event_message(msg["id"], data))

    @callback
    def unsub():
        # pylint: disable=comparison-with-callable
        if registered_channels.get(webhook_id) == forward_push_notification:
            registered_channels.pop(webhook_id)

    registered_channels[webhook_id] = forward_push_notification
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"])
