"""Webhooks used by rachio."""

from __future__ import annotations

from aiohttp import web

from homeassistant.components import cloud, webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, URL_API
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_CLOUDHOOK_URL,
    DOMAIN,
    KEY_EXTERNAL_ID,
    KEY_TYPE,
    SIGNAL_RACHIO_CONTROLLER_UPDATE,
    SIGNAL_RACHIO_RAIN_DELAY_UPDATE,
    SIGNAL_RACHIO_RAIN_SENSOR_UPDATE,
    SIGNAL_RACHIO_SCHEDULE_UPDATE,
    SIGNAL_RACHIO_ZONE_UPDATE,
)
from .device import RachioPerson

# Device webhook values
TYPE_CONTROLLER_STATUS = "DEVICE_STATUS"
SUBTYPE_OFFLINE = "OFFLINE"
SUBTYPE_ONLINE = "ONLINE"
SUBTYPE_OFFLINE_NOTIFICATION = "OFFLINE_NOTIFICATION"
SUBTYPE_COLD_REBOOT = "COLD_REBOOT"
SUBTYPE_SLEEP_MODE_ON = "SLEEP_MODE_ON"
SUBTYPE_SLEEP_MODE_OFF = "SLEEP_MODE_OFF"
SUBTYPE_BROWNOUT_VALVE = "BROWNOUT_VALVE"

# Rain delay values
TYPE_RAIN_DELAY_STATUS = "RAIN_DELAY"
SUBTYPE_RAIN_DELAY_ON = "RAIN_DELAY_ON"
SUBTYPE_RAIN_DELAY_OFF = "RAIN_DELAY_OFF"

# Rain sensor values
TYPE_RAIN_SENSOR_STATUS = "RAIN_SENSOR_DETECTION"
SUBTYPE_RAIN_SENSOR_DETECTION_ON = "RAIN_SENSOR_DETECTION_ON"
SUBTYPE_RAIN_SENSOR_DETECTION_OFF = "RAIN_SENSOR_DETECTION_OFF"

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
SUBTYPE_ZONE_PAUSED = "ZONE_PAUSED"

# Webhook callbacks
LISTEN_EVENT_TYPES = [
    "DEVICE_STATUS_EVENT",
    "ZONE_STATUS_EVENT",
    "RAIN_DELAY_EVENT",
    "RAIN_SENSOR_DETECTION_EVENT",
    "SCHEDULE_STATUS_EVENT",
]
WEBHOOK_CONST_ID = "homeassistant.rachio:"
WEBHOOK_PATH = URL_API + DOMAIN

SIGNAL_MAP = {
    TYPE_CONTROLLER_STATUS: SIGNAL_RACHIO_CONTROLLER_UPDATE,
    TYPE_RAIN_DELAY_STATUS: SIGNAL_RACHIO_RAIN_DELAY_UPDATE,
    TYPE_RAIN_SENSOR_STATUS: SIGNAL_RACHIO_RAIN_SENSOR_UPDATE,
    TYPE_SCHEDULE_STATUS: SIGNAL_RACHIO_SCHEDULE_UPDATE,
    TYPE_ZONE_STATUS: SIGNAL_RACHIO_ZONE_UPDATE,
}


@callback
def async_register_webhook(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register a webhook."""
    webhook_id: str = entry.data[CONF_WEBHOOK_ID]

    async def _async_handle_rachio_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle webhook calls from the server."""
        person: RachioPerson = hass.data[DOMAIN][entry.entry_id]
        data = await request.json()

        try:
            assert (
                data.get(KEY_EXTERNAL_ID, "").split(":")[1]
                == person.rachio.webhook_auth
            )
        except (AssertionError, IndexError):
            return web.Response(status=web.HTTPForbidden.status_code)

        update_type = data[KEY_TYPE]
        if update_type in SIGNAL_MAP:
            async_dispatcher_send(hass, SIGNAL_MAP[update_type], data)

        return web.Response(status=web.HTTPNoContent.status_code)

    webhook.async_register(
        hass, DOMAIN, "Rachio", webhook_id, _async_handle_rachio_webhook
    )


@callback
def async_unregister_webhook(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unregister a webhook."""
    webhook_id: str = entry.data[CONF_WEBHOOK_ID]
    webhook.async_unregister(hass, webhook_id)


async def async_get_or_create_registered_webhook_id_and_url(
    hass: HomeAssistant, entry: ConfigEntry
) -> str:
    """Generate webhook url."""
    config = entry.data.copy()

    updated_config = False
    webhook_url = None

    if not (webhook_id := config.get(CONF_WEBHOOK_ID)):
        webhook_id = webhook.async_generate_id()
        config[CONF_WEBHOOK_ID] = webhook_id
        updated_config = True

    if cloud.async_active_subscription(hass):
        if not (cloudhook_url := config.get(CONF_CLOUDHOOK_URL)):
            cloudhook_url = await cloud.async_create_cloudhook(hass, webhook_id)
            config[CONF_CLOUDHOOK_URL] = cloudhook_url
            updated_config = True
        webhook_url = cloudhook_url

    if not webhook_url:
        webhook_url = webhook.async_generate_url(hass, webhook_id)

    if updated_config:
        hass.config_entries.async_update_entry(entry, data=config)

    return webhook_url
