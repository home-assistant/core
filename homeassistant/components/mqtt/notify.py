"""Support for MQTT notify."""
from __future__ import annotations

import functools
import logging
from typing import Any, Final, TypedDict, cast

import voluptuous as vol

from homeassistant.components import notify
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.template import Template
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
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    async_setup_entry_helper,
    cleanup_device_registry,
    device_info_from_config,
)

CONF_TARGETS: Final = "targets"
CONF_TITLE: Final = "title"
CONF_CONFIG_ENTRY: Final = "config_entry"
CONF_DISCOVER_HASH: Final = "discovery_hash"

MQTT_NOTIFY_SERVICES_SETUP = "mqtt_notify_services_setup"

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Required(CONF_NAME): cv.string,
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


class MqttNotificationConfig(TypedDict, total=False):
    """Supply service parameters for MqttNotificationService."""

    command_topic: str
    command_template: Template
    encoding: str
    name: str | None
    qos: int
    retain: bool
    targets: list
    title: str
    device: ConfigType


async def async_initialize(hass: HomeAssistant) -> None:
    """Initialize globals."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    hass.data.setdefault(MQTT_NOTIFY_SERVICES_SETUP, {})


def device_has_notify_services(hass: HomeAssistant, device_id: str) -> bool:
    """Check if the device has registered notify services."""
    if MQTT_NOTIFY_SERVICES_SETUP not in hass.data:
        return False
    for key, service in hass.data[  # pylint: disable=unused-variable
        MQTT_NOTIFY_SERVICES_SETUP
    ].items():
        if service.device_id == device_id:
            return True
    return False


def _check_notify_service_name(
    hass: HomeAssistant, config: MqttNotificationConfig
) -> str | None:
    """Check if the service already exists or else return the service name."""
    service_name = slugify(config[CONF_NAME])
    has_services = hass.services.has_service(notify.DOMAIN, service_name)
    services = hass.data[MQTT_NOTIFY_SERVICES_SETUP]
    if service_name in services.keys() or has_services:
        _LOGGER.error(
            "Notify service '%s' already exists, cannot register service",
            service_name,
        )
        return None
    return service_name


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT notify service dynamically through MQTT discovery."""
    await async_initialize(hass)
    setup = functools.partial(_async_setup_notify, hass, config_entry=config_entry)
    await async_setup_entry_helper(hass, notify.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_notify(
    hass,
    legacy_config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: dict[str, Any],
):
    """Set up the MQTT notify service with auto discovery."""
    config: MqttNotificationConfig = DISCOVERY_SCHEMA(
        discovery_data[ATTR_DISCOVERY_PAYLOAD]
    )
    discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]

    if not (service_name := _check_notify_service_name(hass, config)):
        async_dispatcher_send(hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None)
        clear_discovery_hash(hass, discovery_hash)
        return

    device_id = _update_device(hass, config_entry, config)

    service = MqttNotificationService(
        hass,
        config,
        config_entry,
        device_id,
        discovery_hash,
    )
    hass.data[MQTT_NOTIFY_SERVICES_SETUP][service_name] = service

    await service.async_setup(hass, service_name, service_name)
    await service.async_register_services()


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MqttNotificationService | None:
    """Prepare the MQTT notification service through configuration.yaml."""
    await async_initialize(hass)
    notification_config: MqttNotificationConfig = cast(MqttNotificationConfig, config)

    if not (service_name := _check_notify_service_name(hass, notification_config)):
        return None

    service = hass.data[MQTT_NOTIFY_SERVICES_SETUP][
        service_name
    ] = MqttNotificationService(
        hass,
        notification_config,
    )
    return service


class MqttNotificationServiceUpdater:
    """Add support for auto discovery updates."""

    def __init__(self, hass: HomeAssistant, service: MqttNotificationService) -> None:
        """Initialize the update service."""

        async def async_discovery_update(
            discovery_payload: DiscoveryInfoType | None,
        ) -> None:
            """Handle discovery update."""
            if not discovery_payload:
                # unregister notify service through auto discovery
                async_dispatcher_send(
                    hass, MQTT_DISCOVERY_DONE.format(service.discovery_hash), None
                )
                await async_tear_down_service()
                return

            # update notify service through auto discovery
            await service.async_update_service(discovery_payload)
            _LOGGER.debug(
                "Notify service %s updated has been processed",
                service.discovery_hash,
            )
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(service.discovery_hash), None
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
            services = hass.data[MQTT_NOTIFY_SERVICES_SETUP]
            if self._service.service_name in services.keys():
                del services[self._service.service_name]
            if not self._device_removed and service.config_entry:
                self._device_removed = True
                await cleanup_device_registry(
                    hass, service.device_id, service.config_entry.entry_id
                )
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
        service_config: MqttNotificationConfig,
        config_entry: ConfigEntry | None = None,
        device_id: str | None = None,
        discovery_hash: tuple | None = None,
    ) -> None:
        """Initialize the service."""
        self.hass = hass
        self._config = service_config
        self._commmand_template = MqttCommandTemplate(
            service_config.get(CONF_COMMAND_TEMPLATE), hass=hass
        )
        self._device_id = device_id
        self._discovery_hash = discovery_hash
        self._config_entry = config_entry
        self._service_name = slugify(service_config[CONF_NAME])

        self._updater = (
            MqttNotificationServiceUpdater(hass, self) if discovery_hash else None
        )

    @property
    def device_id(self) -> str | None:
        """Return the device ID."""
        return self._device_id

    @property
    def config_entry(self) -> ConfigEntry | None:
        """Return the config_entry."""
        return self._config_entry

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
        config: MqttNotificationConfig = DISCOVERY_SCHEMA(discovery_payload)
        # Do not rename a service if that service_name is already in use
        if (
            new_service_name := slugify(config[CONF_NAME])
        ) != self._service_name and _check_notify_service_name(
            self.hass, config
        ) is None:
            return
        # Only refresh services if service name or targets have changes
        if (
            new_service_name != self._service_name
            or config[CONF_TARGETS] != self._config[CONF_TARGETS]
        ):
            services = self.hass.data[MQTT_NOTIFY_SERVICES_SETUP]
            await self.async_unregister_services()
            if self._service_name in services:
                del services[self._service_name]
            self._config = config
            self._service_name = new_service_name
            await self.async_register_services()
            services[new_service_name] = self
        else:
            self._config = config
        self._commmand_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE), hass=self.hass
        )
        _update_device(self.hass, self._config_entry, config)

    @property
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        return {target: target for target in self._config[CONF_TARGETS]}

    async def async_send_message(self, message: str = "", **kwargs):
        """Build and send a MQTT message."""
        target = kwargs.get(notify.ATTR_TARGET)
        if (
            target is not None
            and self._config[CONF_TARGETS]
            and set(target) & set(self._config[CONF_TARGETS]) != set(target)
        ):
            _LOGGER.error(
                "Cannot send %s, target list %s is invalid, valid available targets: %s",
                message,
                target,
                self._config[CONF_TARGETS],
            )
            return
        variables = {
            "message": message,
            "name": self._config[CONF_NAME],
            "service": self._service_name,
            "target": target or self._config[CONF_TARGETS],
            "title": kwargs.get(notify.ATTR_TITLE, self._config[CONF_TITLE]),
        }
        variables.update(kwargs.get(notify.ATTR_DATA) or {})
        payload = self._commmand_template.async_render(
            message,
            variables=variables,
        )
        await mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )


def _update_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry | None,
    config: MqttNotificationConfig,
) -> str | None:
    """Update device registry."""
    if config_entry is None or CONF_DEVICE not in config:
        return None

    device = None
    device_registry = dr.async_get(hass)
    config_entry_id = config_entry.entry_id
    device_info = device_info_from_config(config[CONF_DEVICE])

    if config_entry_id is not None and device_info is not None:
        update_device_info = cast(dict, device_info)
        update_device_info["config_entry_id"] = config_entry_id
        device = device_registry.async_get_or_create(**update_device_info)

    return device.id if device else None
