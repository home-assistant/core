"""Support for MQTT notify."""
from __future__ import annotations

import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import notify
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import PLATFORMS, MqttCommandTemplate
from .. import mqtt
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    DOMAIN,
)
from .discovery import MQTT_DISCOVERY_DONE, MQTT_DISCOVERY_UPDATED, clear_discovery_hash
from .mixins import (
    CONF_CONNECTIONS,
    CONF_IDENTIFIERS,
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    async_setup_entry_helper,
    cleanup_device_registry,
    device_info_from_config,
)

CONF_TARGETS = "targets"
CONF_TITLE = "title"

MQTT_NOTIFY_SERVICES_SETUP = "mqtt_notify_services_setup"

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TARGETS, default=[]): cv.ensure_list,
        vol.Optional(CONF_TITLE, default=notify.ATTR_TITLE_DEFAULT): cv.string,
        vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
    }
)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    },
    extra=vol.REMOVE_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Set up MQTT climate device dynamically through MQTT discovery."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    setup = functools.partial(_async_setup_notify, hass, config_entry=config_entry)
    await async_setup_entry_helper(hass, notify.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_notify(
    hass,
    legacy_config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: dict[str, Any],
):
    """Set up the MQTT notify service with auto discovery."""
    config = DISCOVERY_SCHEMA(discovery_data[ATTR_DISCOVERY_PAYLOAD])
    service_name = slugify(config.get(CONF_NAME) or DOMAIN)
    services = hass.data.setdefault(MQTT_NOTIFY_SERVICES_SETUP, set())
    has_services = hass.services.has_service(notify.DOMAIN, service_name)
    discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
    if service_name in services or has_services:
        _LOGGER.error(
            "Notify service '%s' already exists, cannot register service(s)",
            service_name,
        )
        async_dispatcher_send(hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None)
        clear_discovery_hash(hass, discovery_hash)
        return
    services.add(service_name)
    device_id = None
    if CONF_DEVICE in config:
        await _update_device(hass, config_entry, config)

        device_registry = await hass.helpers.device_registry.async_get_registry()
        device = device_registry.async_get_device(
            {(DOMAIN, id_) for id_ in config[CONF_DEVICE][CONF_IDENTIFIERS]},
            {tuple(x) for x in config[CONF_DEVICE][CONF_CONNECTIONS]},
        )

        device_id = device.id

    service = MqttNotificationService(
        hass,
        config[CONF_COMMAND_TOPIC],
        MqttCommandTemplate(config.get(CONF_COMMAND_TEMPLATE), hass=hass),
        config[CONF_ENCODING],
        config.get(CONF_NAME),
        config[CONF_QOS],
        config[CONF_RETAIN],
        config[CONF_TARGETS],
        config[CONF_TITLE],
        discovery_hash=discovery_hash,
        device_id=device_id,
        config_entry=config_entry,
    )
    await service.async_setup(hass, service_name, service_name)
    await service.async_register_services()


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MqttNotificationService | None:
    """Prepare the MQTT notification service through configuration.yaml."""
    name = config.get(CONF_NAME)
    if CONF_NAME not in config:
        config[CONF_NAME] = DOMAIN
    service_name = slugify(name or DOMAIN)
    services = hass.data.setdefault(MQTT_NOTIFY_SERVICES_SETUP, set())
    has_services = hass.services.has_service(notify.DOMAIN, service_name)
    if service_name in services or has_services:
        _LOGGER.error(
            "Notify service '%s' is not unique, cannot register service(s)",
            service_name,
        )
        return None
    services.add(service_name)
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    return MqttNotificationService(
        hass,
        config[CONF_COMMAND_TOPIC],
        MqttCommandTemplate(config.get(CONF_COMMAND_TEMPLATE), hass=hass),
        config[CONF_ENCODING],
        name,
        config[CONF_QOS],
        config[CONF_RETAIN],
        config[CONF_TARGETS],
        config[CONF_TITLE],
    )


class MqttNotificationServiceUpdater:
    """Add support for auto discovery updates."""

    def __init__(self, hass: HomeAssistant, service: MqttNotificationService) -> None:
        """Initialize the update service."""

        async def async_discovery_update(
            discovery_payload: DiscoveryInfoType | None,
        ) -> None:
            """Handle discovery update."""
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(service.discovery_hash), None
            )
            if not discovery_payload:
                # unregister notify service through auto discovery
                await async_tear_down_service()
                return

            # update notify service through auto discovery
            await service.async_update_service(discovery_payload)
            _LOGGER.debug(
                "Notify service %s updated has been processed",
                service.discovery_hash,
            )

        async def async_device_removed(event):
            """Handle the removal of a device."""
            device_id = event.data["device_id"]
            if (
                event.data["action"] != "remove"
                or device_id != service.device_id
                or self._device_removed
            ):
                return
            self._device_removed = True
            await async_tear_down_service()

        async def async_tear_down_service():
            """Handle the removal of the service."""
            services = hass.data.setdefault(MQTT_NOTIFY_SERVICES_SETUP, set())
            if self._service.service_name in services:
                services.remove(self._service.service_name)
            if not self._device_removed and service.device_id:
                self._device_removed = True
                await cleanup_device_registry(hass, service.device_id)
            clear_discovery_hash(hass, service.discovery_hash)
            self._remove_discovery()
            await service.async_unregister_services()
            _LOGGER.info(
                "Notify service %s has been removed",
                service.discovery_hash,
            )
            del self._service

        self._service = service
        self._remove_discovery = async_dispatcher_connect(
            hass,
            MQTT_DISCOVERY_UPDATED.format(service.discovery_hash),
            async_discovery_update,
        )
        if service.device_id:
            self._remove_device_updated = hass.bus.async_listen(
                EVENT_DEVICE_REGISTRY_UPDATED, async_device_removed
            )
        self._device_removed = False
        async_dispatcher_send(
            hass, MQTT_DISCOVERY_DONE.format(service.discovery_hash), None
        )
        _LOGGER.info(
            "Notify service %s has been initialized",
            service.discovery_hash,
        )


class MqttNotificationService(notify.BaseNotificationService):
    """Implement the notification service for MQTT."""

    def __init__(
        self,
        hass: HomeAssistant,
        command_topic: str,
        command_template: MqttCommandTemplate,
        encoding: str,
        name: str | None,
        qos: int,
        retain: bool,
        targets: list,
        title: str | None,
        discovery_hash: tuple | None = None,
        device_id: str | None = None,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the service."""
        self.hass = hass
        self._command_topic = command_topic
        self._command_template = command_template
        self._encoding = encoding
        self._name = name
        self._qos = qos
        self._retain = retain
        self._targets = targets
        self._title = title
        self._discovery_hash = discovery_hash
        self._device_id = device_id
        self._config_entry = config_entry
        self._service_name = slugify(name or DOMAIN)

        self._updater = (
            MqttNotificationServiceUpdater(hass, self) if discovery_hash else None
        )

    @property
    def device_id(self) -> str | None:
        """Return the device ID."""
        return self._device_id

    @property
    def discovery_hash(self) -> tuple | None:
        """Return the discovery hash."""
        return self._discovery_hash

    @property
    def service_name(self) -> str:
        """Return the service ma,e."""
        return self._service_name

    async def async_update_service(
        self,
        discovery_payload: DiscoveryInfoType,
    ) -> None:
        """Update the notify service through auto discovery."""
        config = DISCOVERY_SCHEMA(discovery_payload)
        new_service_name = slugify(config.get(CONF_NAME, DOMAIN))
        if new_service_name != self._service_name and self.hass.services.has_service(
            notify.DOMAIN, new_service_name
        ):
            _LOGGER.error(
                "Notify service '%s' already exists, cannot update the existing service(s)",
                new_service_name,
            )
            return
        self._command_topic = config[CONF_COMMAND_TOPIC]
        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE), hass=self.hass
        )
        self._encoding = config[CONF_ENCODING]
        self._name = config.get(CONF_NAME)
        self._qos = config[CONF_QOS]
        self._retain = config[CONF_RETAIN]
        self._title = config[CONF_TITLE]
        if (
            new_service_name != self._service_name
            or config[CONF_TARGETS] != self._targets
        ):
            services = self.hass.data.setdefault(MQTT_NOTIFY_SERVICES_SETUP, set())
            await self.async_unregister_services()
            if self._service_name in services:
                services.remove(self._service_name)
            self._targets = config[CONF_TARGETS]
            self._service_name = new_service_name
            await self.async_register_services()
            services.add(new_service_name)
        if self.device_id:
            await _update_device(self.hass, self._config_entry, config)

    @property
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        return {target: target for target in self._targets}

    async def async_send_message(self, message: str = "", **kwargs):
        """Build and send a MQTT message."""
        target = kwargs.get(notify.ATTR_TARGET)
        if (
            target is not None
            and self._targets
            and set(target) & set(self._targets) != set(target)
        ):
            _LOGGER.error(
                "Cannot send %s, target list %s is invalid, valid available targets: %s",
                message,
                target,
                self._targets,
            )
            return
        variables = {
            "message": message,
            "name": self._name,
            "service": self._service_name,
            "target": target or self._targets,
            "title": kwargs.get(notify.ATTR_TITLE, self._title),
        }
        variables.update(kwargs.get(notify.ATTR_DATA) or {})
        payload = self._command_template.async_render(
            message,
            variables=variables,
        )
        await mqtt.async_publish(
            self.hass,
            self._command_topic,
            payload,
            self._qos,
            self._retain,
            self._encoding,
        )


async def _update_device(hass, config_entry, config):
    """Update device registry."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    config_entry_id = config_entry.entry_id
    device_info = device_info_from_config(config[CONF_DEVICE])

    if config_entry_id is not None and device_info is not None:
        device_info["config_entry_id"] = config_entry_id
        device_registry.async_get_or_create(**device_info)
