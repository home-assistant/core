"""Support for MQTT actions."""

import asyncio
from datetime import datetime

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigValidationError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, event as ev
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.async_ import create_eager_task

from .client import async_subscribe_internal
from .const import (
    ATTR_EVALUATE_PAYLOAD,
    ATTR_MESSAGE_EXPIRY_INTERVAL,
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
    DOMAIN,
    ENTITY_PLATFORMS,
    LOGGER,
    SERVICE_DUMP,
    SERVICE_PUBLISH,
)
from .models import (
    DATA_MQTT,
    PublishPayloadType,
    ReceiveMessage,
    convert_outgoing_mqtt_payload,
)
from .util import (
    async_check_config_schema,
    async_forward_entry_setup_and_setup_discovery,
    async_remove_mqtt_issues,
    mqtt_config_entry_enabled,
    platforms_from_config,
    valid_publish_topic,
    valid_qos_schema,
    valid_subscribe_topic,
)

# Publish action call validation schema
MQTT_PUBLISH_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_TOPIC): valid_publish_topic,
        probatio.Required(ATTR_PAYLOAD, default=None): probatio.Any(cv.string, None),
        probatio.Optional(ATTR_EVALUATE_PAYLOAD): cv.boolean,
        probatio.Optional(ATTR_QOS, default=DEFAULT_QOS): valid_qos_schema,
        probatio.Optional(ATTR_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        probatio.Optional(ATTR_MESSAGE_EXPIRY_INTERVAL): cv.positive_time_period_dict,
    },
    required=True,
)

MQTT_DUMP_SCHEMA = probatio.Schema(
    {
        probatio.Required("topic"): valid_subscribe_topic,
        probatio.Optional("duration", default=5): int,
    }
)


async def _async_publish_service(call: ServiceCall) -> None:
    """Handle MQTT publish service calls."""
    hass = call.hass
    msg_topic: str = call.data[ATTR_TOPIC]

    if not mqtt_config_entry_enabled(hass):
        raise ServiceValidationError(
            translation_key="mqtt_not_setup_cannot_publish",
            translation_domain=DOMAIN,
            translation_placeholders={"topic": msg_topic},
        )

    mqtt_data = hass.data[DATA_MQTT]
    payload: PublishPayloadType = call.data[ATTR_PAYLOAD]
    evaluate_payload: bool = call.data.get(ATTR_EVALUATE_PAYLOAD, False)
    qos: int = call.data[ATTR_QOS]
    retain: bool = call.data[ATTR_RETAIN]
    message_expiry_interval: int | None = (
        int(call.data[ATTR_MESSAGE_EXPIRY_INTERVAL].total_seconds())
        if ATTR_MESSAGE_EXPIRY_INTERVAL in call.data
        else None
    )

    if evaluate_payload:
        # Convert quoted binary literal to raw data
        payload = convert_outgoing_mqtt_payload(payload)

    await mqtt_data.client.async_publish(
        msg_topic,
        payload,
        qos,
        retain,
        message_expiry_interval=message_expiry_interval,
    )


async def _async_dump_service(call: ServiceCall) -> None:
    """Handle MQTT dump service calls."""
    hass = call.hass
    messages: list[tuple[str, str]] = []

    @callback
    def collect_msg(msg: ReceiveMessage) -> None:
        messages.append((msg.topic, str(msg.payload).replace("\n", "")))

    unsub = async_subscribe_internal(hass, call.data["topic"], collect_msg)

    def write_dump() -> None:
        with open(hass.config.path("mqtt_dump.txt"), "w", encoding="utf8") as fp:
            fp.writelines([",".join(msg) + "\n" for msg in messages])

    async def finish_dump(_: datetime) -> None:
        """Write dump to file."""
        unsub()
        await hass.async_add_executor_job(write_dump)

    ev.async_call_later(hass, call.data["duration"], finish_dump)


async def _async_reload_config(call: ServiceCall) -> None:
    """Reload the platforms."""
    hass = call.hass
    if not mqtt_config_entry_enabled(hass):
        LOGGER.debug(
            "Skipped reloading MQTT integration, the MQTT config entry is not enabled"
        )
        return
    entry: ConfigEntry = next(iter(hass.config_entries.async_entries(DOMAIN)))
    mqtt_data = hass.data[DATA_MQTT]

    # Fetch updated manually configured items and validate
    try:
        config_yaml = await async_integration_yaml_config(
            hass, DOMAIN, raise_on_failure=True
        )
    except ConfigValidationError as ex:
        raise ServiceValidationError(
            translation_domain=ex.translation_domain,
            translation_key=ex.translation_key,
            translation_placeholders=ex.translation_placeholders,
        ) from ex

    new_config: list[ConfigType] = config_yaml.get(DOMAIN, [])
    platforms_used = platforms_from_config(new_config)
    new_platforms = platforms_used - mqtt_data.platforms_loaded
    await async_forward_entry_setup_and_setup_discovery(hass, entry, new_platforms)
    # Check the schema before continuing reload
    await async_check_config_schema(hass, config_yaml)

    # Remove repair issues
    async_remove_mqtt_issues(hass, mqtt_data)

    mqtt_data.config = new_config

    # Reload the modern yaml platforms
    mqtt_platforms = async_get_platforms(hass, DOMAIN)
    tasks = [
        create_eager_task(entity.async_remove())
        for mqtt_platform in mqtt_platforms
        for entity in list(mqtt_platform.entities.values())
        if getattr(entity, "_discovery_data", None) is None
        and mqtt_platform.config_entry
        and mqtt_platform.domain in ENTITY_PLATFORMS
    ]
    await asyncio.gather(*tasks)

    for component in mqtt_data.reload_handlers.values():
        component()

    # Fire event
    hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the actions for the MQTT component."""

    async_register_admin_service(
        hass, DOMAIN, SERVICE_PUBLISH, _async_publish_service, MQTT_PUBLISH_SCHEMA
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_DUMP, _async_dump_service, MQTT_DUMP_SCHEMA
    )
    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _async_reload_config)
