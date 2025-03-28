"""Foscam component for Home Assistant."""

import base64
from datetime import datetime
import logging

from coordinator import FoscamConfigEntry

from homeassistant.components import webhook
from homeassistant.components.persistent_notification import (
    create as create_notification,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)
DOMAIN = "my_custom_integration"
WEBHOOK_ID = "my_custom_webhook"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FoscamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the custom integration."""
    coordinator = config_entry.runtime_data

    webhook.async_register(
        hass, DOMAIN, "My Custom Integration Webhook", WEBHOOK_ID, handle_webhook
    )
    # 生成 webhook URL 并设置到设备
    webhook_url = hass.components.webhook.async_generate_url(WEBHOOK_ID)
    encoded_url = base64.urlsafe_b64encode(webhook_url.encode("utf-8")).decode("utf-8")
    await hass.async_add_executor_job(
        coordinator.session.setAlarmHttpServer, encoded_url
    )


async def handle_webhook(hass: HomeAssistant, webhook_id: str, request):
    """Handle incoming webhook requests."""
    try:
        data = await request.json()

        alarm_device_name = data.get("devname")
        alarm_type = int(data.get("alarm_type"))
        alarm_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if alarm_type == 0:
            message = "Motion detection triggered on " + alarm_time
        elif alarm_type == 1:
            message = "Sound detection triggered on " + alarm_time
        elif alarm_type == 5:
            message = "Human detection triggered on " + alarm_time
        elif alarm_type == 9:
            message = "The doorbell button will be triggered at " + alarm_time
        elif alarm_type == 12:
            message = "Face detection triggered on " + alarm_time
        elif alarm_type == 13:
            message = "Car detection triggered on " + alarm_time
        elif alarm_type == 14:
            message = "Pet detection triggered on " + alarm_time

        create_notification(
            hass,
            title=alarm_device_name,
            message=message,
            notification_id="device_alarm",
        )

    except (ValueError, TypeError) as e:
        _LOGGER.error("Error handling webhook: %s", e)
