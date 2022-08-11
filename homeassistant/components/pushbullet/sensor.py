"""Pushbullet platform for sensor component."""
from __future__ import annotations

import logging
import threading
from typing import Any

from pushbullet import Listener, PushBullet
import voluptuous as vol

from homeassistant.components.repairs.issue_handler import async_create_issue
from homeassistant.components.repairs.models import IssueSeverity
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_UPDATED, DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="application_name",
        name="Application name",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="body",
        name="Body",
    ),
    SensorEntityDescription(
        key="notification_id",
        name="Notification ID",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="notification_tag",
        name="Notification tag",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="package_name",
        name="Package name",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="receiver_email",
        name="Receiver email",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="sender_email",
        name="Sender email",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="source_device_iden",
        name="Sender device ID",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="title",
        name="Title",
    ),
    SensorEntityDescription(
        key="type",
        name="Type",
        entity_registry_enabled_default=False,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["title", "body"]): vol.All(
            cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_KEYS)]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Pushbullet Sensor platform."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2022.11.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Pushbullet sensors from config entry."""

    pushbullet: PushBullet = hass.data[DOMAIN][entry.entry_id]
    pb_provider = PushBulletNotificationProvider(hass, pushbullet)
    entities = [
        PushBulletNotificationSensor(hass, entry, pb_provider, description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class PushBulletNotificationSensor(SensorEntity):
    """Representation of a Pushbullet Sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pb_provider: PushBulletNotificationProvider,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Pushbullet sensor."""
        self.hass = hass
        self.entity_description = description
        self.pb_provider = pb_provider
        self._attr_unique_id = f"{entry.entry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_API_KEY])},
            name=entry.data[CONF_NAME],
            entry_type=DeviceEntryType.SERVICE,
        )

    @callback
    def async_update_callback(self) -> None:
        """Fetch the latest data from the sensor.

        This will fetch the 'sensor reading' into self._state but also all
        attributes into self._state_attributes.
        """
        try:
            self._attr_native_value = self.pb_provider.data[self.entity_description.key]
            self._attr_extra_state_attributes = self.pb_provider.data
        except (KeyError, TypeError):
            pass
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DATA_UPDATED, self.async_update_callback
            )
        )


class PushBulletNotificationProvider(threading.Thread):
    """Provider for an account, leading to one or more sensors."""

    def __init__(self, hass: HomeAssistant, pushbullet: PushBullet) -> None:
        """Start to retrieve pushes from the given Pushbullet instance."""

        super().__init__()
        self.hass = hass
        self.pushbullet = pushbullet
        self.data: dict[str, Any] = {}
        self.listener = Listener(account=pushbullet, on_push=self.on_push)
        self.daemon = True
        self.start()

    def on_push(self, data: dict[str, Any]) -> None:
        """Update the current data.

        Currently only monitors pushes but might be extended to monitor
        different kinds of Pushbullet events.
        """
        if data["type"] == "push":
            self.data = data["push"]
        dispatcher_send(self.hass, DATA_UPDATED)

    def run(self):
        """Retrieve_pushes.

        Spawn a new Listener and links it to self.on_push.
        """

        _LOGGER.debug("Getting pushes")
        try:
            self.listener.run_forever()
        finally:
            self.listener.close()
