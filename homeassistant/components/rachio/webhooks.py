"""Webhooks used by rachio."""

import logging

from aiohttp import web

from homeassistant.const import URL_API
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_CLOUDHOOK_URL,
    CONF_WEBHOOK_ID,
    DOMAIN,
    KEY_EXTERNAL_ID,
    KEY_TYPE,
    SIGNAL_RACHIO_CONTROLLER_UPDATE,
    SIGNAL_RACHIO_SCHEDULE_UPDATE,
    SIGNAL_RACHIO_ZONE_UPDATE,
)

# Device webhook values
TYPE_CONTROLLER_STATUS = "DEVICE_STATUS"
SUBTYPE_OFFLINE = "OFFLINE"
SUBTYPE_ONLINE = "ONLINE"
SUBTYPE_OFFLINE_NOTIFICATION = "OFFLINE_NOTIFICATION"
SUBTYPE_COLD_REBOOT = "COLD_REBOOT"
SUBTYPE_SLEEP_MODE_ON = "SLEEP_MODE_ON"
SUBTYPE_SLEEP_MODE_OFF = "SLEEP_MODE_OFF"
SUBTYPE_BROWNOUT_VALVE = "BROWNOUT_VALVE"
SUBTYPE_RAIN_SENSOR_DETECTION_ON = "RAIN_SENSOR_DETECTION_ON"
SUBTYPE_RAIN_SENSOR_DETECTION_OFF = "RAIN_SENSOR_DETECTION_OFF"
SUBTYPE_RAIN_DELAY_ON = "RAIN_DELAY_ON"
SUBTYPE_RAIN_DELAY_OFF = "RAIN_DELAY_OFF"

# Schedule webhook values
TYPE_SCHEDULE_STATUS = "SCHEDULE_STATUS"
SUBTYPE_SCHEDULE_STARTED = "SCHEDULE_STARTED"
SUBTYPE_SCHEDULE_STOPPED = "SCHEDULE_STOPPED"
SUBTYPE_SCHEDULE_COMPLETED = "SCHEDULE_COMPLETED"
SUBTYPE_WEATHER_NO_SKIP = "WEATHER_INTELLIGENCE_NO_SKIP"
SUBTYPE_WEATHER_SKIP = "WEATHER_INTELLIGENCE_SKIP"
SUBTYPE_WEATHER_CLIMATE_SKIP = "WEATHER_INTELLIGENCE_CLIMATE_SKIP"
SUBTYPE_WEATHER_FREEZE = "WEATHER_INTELLIGENCE_FREEZE"

# Zone webhook values
TYPE_ZONE_STATUS = "ZONE_STATUS"
SUBTYPE_ZONE_STARTED = "ZONE_STARTED"
SUBTYPE_ZONE_STOPPED = "ZONE_STOPPED"
SUBTYPE_ZONE_COMPLETED = "ZONE_COMPLETED"
SUBTYPE_ZONE_CYCLING = "ZONE_CYCLING"
SUBTYPE_ZONE_CYCLING_COMPLETED = "ZONE_CYCLING_COMPLETED"

# Webhook callbacks
LISTEN_EVENT_TYPES = [
    "DEVICE_STATUS_EVENT",
    "ZONE_STATUS_EVENT",
    "SCHEDULE_STATUS_EVENT",
]
WEBHOOK_CONST_ID = "homeassistant.rachio:"
WEBHOOK_PATH = URL_API + DOMAIN

SIGNAL_MAP = {
    TYPE_CONTROLLER_STATUS: SIGNAL_RACHIO_CONTROLLER_UPDATE,
    TYPE_SCHEDULE_STATUS: SIGNAL_RACHIO_SCHEDULE_UPDATE,
    TYPE_ZONE_STATUS: SIGNAL_RACHIO_ZONE_UPDATE,
}


_LOGGER = logging.getLogger(__name__)


@callback
def async_register_webhook(hass, webhook_id, entry_id):
    """Register a webhook."""

    async def _async_handle_rachio_webhook(hass, webhook_id, request):
        """Handle webhook calls from the server."""
        data = await request.json()

        try:
            auth = data.get(KEY_EXTERNAL_ID, "").split(":")[1]
            assert auth == hass.data[DOMAIN][entry_id].rachio.webhook_auth
        except (AssertionError, IndexError):
            return web.Response(status=web.HTTPForbidden.status_code)

        update_type = data[KEY_TYPE]
        if update_type in SIGNAL_MAP:
            async_dispatcher_send(hass, SIGNAL_MAP[update_type], data)

        return web.Response(status=web.HTTPNoContent.status_code)

    hass.components.webhook.async_register(
        DOMAIN, "Rachio", webhook_id, _async_handle_rachio_webhook
    )


async def async_get_or_create_registered_webhook_id_and_url(hass, entry):
    """Generate webhook ID."""
    config = entry.data.copy()

    updated_config = False
    webhook_url = None

    webhook_id = config.get(CONF_WEBHOOK_ID)
    if not webhook_id:
        webhook_id = hass.components.webhook.async_generate_id()
        config[CONF_WEBHOOK_ID] = webhook_id
        updated_config = True

    if hass.components.cloud.async_active_subscription():
        cloudhook_url = config.get(CONF_CLOUDHOOK_URL)
        if not cloudhook_url:
            cloudhook_url = await hass.components.cloud.async_create_cloudhook(
                webhook_id
            )
            config[CONF_CLOUDHOOK_URL] = cloudhook_url
            updated_config = True
        webhook_url = cloudhook_url

    if not webhook_url:
        webhook_url = hass.components.webhook.async_generate_url(webhook_id)

    if updated_config:
        hass.config_entries.async_update_entry(entry, data=config)

    return webhook_id, webhook_url
