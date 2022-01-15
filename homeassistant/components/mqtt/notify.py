"""Support for MQTT nonify."""
from __future__ import annotations

import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import notify
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SERVICE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PLATFORMS, MqttCommandTemplate
from .. import mqtt
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    DOMAIN,
)
from .discovery import MQTT_DISCOVERY_DONE, MQTT_DISCOVERY_UPDATED, clear_discovery_hash
from .mixins import async_setup_entry_helper

CONF_COMMAND_TEMPLATE = "command_template"
CONF_PAYLOAD_TITLE = "Notification"
CONF_TARGET = "target"
CONF_TITLE = "title"

MQTT_NOTIFY_TARGET_CONFIG = "mqtt_notify_target_config"

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_TARGET): cv.string,
        vol.Optional(CONF_TITLE, default=notify.ATTR_TITLE_DEFAULT): cv.string,
        vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
    }
)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA.extend({}, extra=vol.REMOVE_EXTRA)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Set up MQTT climate device dynamically through MQTT discovery."""
    setup = functools.partial(_async_setup_notify, hass, config_entry=config_entry)
    await async_setup_entry_helper(hass, notify.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_notify(
    hass, config: ConfigType, config_entry: ConfigEntry, discovery_data: dict[str, Any]
):
    """Set up the MQTT notify service with auto discovery."""

    await _async_setup_service(hass, config)
    notify_config = hass.data.setdefault(
        MQTT_NOTIFY_TARGET_CONFIG,
        {CONF_TARGET: {}, CONF_SERVICE: None},
    )
    # enable support for discovery updates for the new service
    await notify_config[CONF_SERVICE].async_add_updater(discovery_data)


async def _async_setup_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Validate the service configuration setup."""
    notify_config = hass.data.setdefault(
        MQTT_NOTIFY_TARGET_CONFIG,
        {CONF_TARGET: {}, CONF_SERVICE: None},
    )
    if notify_config[CONF_TARGET].get(config[CONF_TARGET]):
        raise ValueError(
            f"Target {config[CONF_TARGET]} in config {dict(config)} is not unique, a notify service for this target has already been setup",
        )

    target_config = notify_config[CONF_TARGET][config[CONF_TARGET]] = {}
    target_config[CONF_COMMAND_TEMPLATE] = MqttCommandTemplate(
        config.get(CONF_COMMAND_TEMPLATE), hass=hass
    ).async_render
    target_config[CONF_COMMAND_TOPIC] = config[CONF_COMMAND_TOPIC]
    target_config[CONF_ENCODING] = config[CONF_ENCODING]
    target_config[CONF_NAME] = config.get(CONF_NAME) or config[CONF_TARGET]
    target_config[CONF_QOS] = config[CONF_QOS]
    target_config[CONF_TITLE] = config[CONF_TITLE]
    target_config[CONF_RETAIN] = config[CONF_RETAIN]

    if notify_config[CONF_SERVICE] is None:
        await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
        notify_config[CONF_SERVICE] = MqttNotificationService(hass)
        await notify_config[CONF_SERVICE].async_setup(hass, DOMAIN, DOMAIN)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MqttNotificationService | None:
    """Prepare the MQTT notification service."""
    await _async_setup_service(hass, config)
    config[CONF_NAME] = DOMAIN
    return hass.data[MQTT_NOTIFY_TARGET_CONFIG][CONF_SERVICE]


class MqttNotificationServiceUpdater:
    """Add support for auto discovery updates."""

    def __init__(self, hass: HomeAssistant, discovery_info: DiscoveryInfoType) -> None:
        """Initialize the update service."""

        async def async_discovery_update(
            discovery_payload: DiscoveryInfoType | None,
        ) -> None:
            """Handle discovery update."""
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(self._discovery_hash), None
            )
            if not discovery_payload:
                # remove notify service
                del hass.data[MQTT_NOTIFY_TARGET_CONFIG][CONF_TARGET][self._target]
                clear_discovery_hash(hass, self._discovery_hash)
                self._remove_discovery()
                await hass.data[MQTT_NOTIFY_TARGET_CONFIG][
                    CONF_SERVICE
                ].async_register_services()
                _LOGGER.info(
                    "Notify service %s for target %s has been removed",
                    self._discovery_hash,
                    self._target,
                )
                return

            # validate the schema
            config = DISCOVERY_SCHEMA(
                discovery_payload["discovery_data"][ATTR_DISCOVERY_PAYLOAD]
            )
            await async_get_service(hass, config)
            await hass.data[MQTT_NOTIFY_TARGET_CONFIG][
                CONF_SERVICE
            ].async_register_services()
            _LOGGER.debug(
                "Notify service %s for target %s has been updated",
                self._discovery_hash,
                self._target,
            )

        self._discovery_hash = discovery_info[ATTR_DISCOVERY_HASH]
        self._target = discovery_info[ATTR_DISCOVERY_PAYLOAD][CONF_TARGET]
        self._remove_discovery = async_dispatcher_connect(
            hass,
            MQTT_DISCOVERY_UPDATED.format(self._discovery_hash),
            async_discovery_update,
        )
        _LOGGER.info(
            "Notify service %s for target %s has been initialized",
            self._discovery_hash,
            self._target,
        )


class MqttNotificationService(notify.BaseNotificationService):
    """Implement the notification service for E-mail messages."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the service."""
        self.hass = hass
        self._config = self.hass.data[MQTT_NOTIFY_TARGET_CONFIG][CONF_TARGET]

    async def async_add_updater(
        self,
        discovery_info: DiscoveryInfoType,
    ) -> None:
        """Add an update hook to support auto discovery updates."""
        discovery_hash = discovery_info[ATTR_DISCOVERY_HASH]
        MqttNotificationServiceUpdater(self.hass, discovery_info)
        await self.hass.data[MQTT_NOTIFY_TARGET_CONFIG][
            CONF_SERVICE
        ].async_register_services()
        async_dispatcher_send(
            self.hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
        )

    @property
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        return {entry[CONF_NAME]: id for id, entry in self._config.items()}

    async def async_send_message(self, message: str = "", **kwargs):
        """Build and send a MQTT message to a target."""
        for target in kwargs.get(notify.ATTR_TARGET, []):
            if (target_config := self._config.get(target)) is None:
                continue
            variables = {
                "data": kwargs.get(notify.ATTR_DATA),
                "message": message,
                "name": target_config[CONF_NAME],
                "target": target,
                "title": kwargs.get(notify.ATTR_TITLE, target_config[CONF_TITLE]),
            }
            payload = target_config[CONF_COMMAND_TEMPLATE](message, variables=variables)
            await mqtt.async_publish(
                self.hass,
                target_config[CONF_COMMAND_TOPIC],
                payload,
                target_config[CONF_QOS],
                target_config[CONF_RETAIN],
                target_config[CONF_ENCODING],
            )
