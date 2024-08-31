"""Pushbullet platform for sensor component."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PushBulletNotificationProvider
from .const import DATA_UPDATED, DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="application_name",
        translation_key="application_name",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="body",
        translation_key="body",
    ),
    SensorEntityDescription(
        key="notification_id",
        translation_key="notification_id",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="notification_tag",
        translation_key="notification_tag",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="package_name",
        translation_key="package_name",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="receiver_email",
        translation_key="receiver_email",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="sender_email",
        translation_key="sender_email",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="source_device_iden",
        translation_key="source_device_identifier",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="title",
        translation_key="title",
    ),
    SensorEntityDescription(
        key="type",
        translation_key="type",
        entity_registry_enabled_default=False,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Pushbullet sensors from config entry."""

    pb_provider: PushBulletNotificationProvider = hass.data[DOMAIN][entry.entry_id]

    entities = [
        PushBulletNotificationSensor(entry.data[CONF_NAME], pb_provider, description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class PushBulletNotificationSensor(SensorEntity):
    """Representation of a Pushbullet Sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        pb_provider: PushBulletNotificationProvider,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Pushbullet sensor."""
        self.entity_description = description
        self.pb_provider = pb_provider
        self._attr_unique_id = (
            f"{pb_provider.pushbullet.user_info['iden']}-{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pb_provider.pushbullet.user_info["iden"])},
            name=name,
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
