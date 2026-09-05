"""Contains numbers configurations for Prism wallbox integration."""

from datetime import datetime
import logging
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import BINARY_SENSOR_DOMAIN
from .entity import PrismBaseEntity
from .entry_data import RuntimeEntryData
from .touch_events import normalize_touch_payload

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    entry_data: RuntimeEntryData = entry.runtime_data
    _LOGGER.debug("async_setup_entry for binary sensors: %s", entry_data)
    binsens = [
        PrismBinarySensor(entry_data, description, 0)
        for description in BASE_BINARYSENSORS
    ]

    ports = entry_data.ports
    for port in range(1, ports + 1):
        binsens.extend(
            [
                PrismErrorBinarySensor(entry_data, description, port)
                for description in ERROR_BINARYSENSORS
            ]
        )
        binsens.extend(
            [
                PrismEventBinarySensor(entry_data, description, port)
                for description in EVENTS_BINARYSENSORS
            ]
        )

    async_add_entities(binsens)


class PrismBinarySensorEntityDescription(
    BinarySensorEntityDescription, frozen_or_thawed=True
):
    """A class that describes prism binary sensor entities."""

    expire_after: float = 600
    topic: str | None = None


class PrismEventBinarySensorEntityDescription(
    PrismBinarySensorEntityDescription, frozen_or_thawed=True
):
    """A class that describes prism button event sensor entities."""

    sequence: tuple[int, ...] = (1,)
    accepted_sequences: tuple[tuple[int, ...], ...] | None = None


class PrismBinarySensor(PrismBaseEntity, BinarySensorEntity):
    """Prism binary sensor entity."""

    _attr_has_entity_name = True

    entity_description: PrismBinarySensorEntityDescription

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        description: PrismBinarySensorEntityDescription,
        port: int,
    ) -> None:
        """Init Prism select."""
        _LOGGER.debug("PrismBinarySensor.__init__: %s", entry_data)
        ismultiport = entry_data.ports > 1
        if not ismultiport:
            device = entry_data.devices[0]
        else:
            device = entry_data.devices[port]
        super().__init__(entry_data, BINARY_SENSOR_DOMAIN, description, device)
        self._attr_is_on = False

    @override
    def _message_received(self, msg) -> None:
        """Update the sensor with the most recent event."""
        self.schedule_expiration_callback()

        # Handle online presence
        if not self._attr_is_on:
            self._attr_is_on = True
            self.schedule_update_ha_state()

    @override
    def _value_is_expired(self):
        """Triggered when value is expired."""
        self._attr_is_on = False

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to mqtt."""
        await self._subscribe_topic()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from mqtt."""
        _LOGGER.debug("async_will_remove_from_hass")
        await super().async_will_remove_from_hass()
        self.cleanup_expiration_trigger()


class PrismErrorBinarySensor(PrismBinarySensor):
    """Prism error binary sensor entity."""

    _attr_has_entity_name = True

    entity_description: PrismBinarySensorEntityDescription

    def _get_description(
        self,
        port: int,
        mulitport: bool,
        description: PrismBinarySensorEntityDescription,
    ) -> PrismBinarySensorEntityDescription:
        if port == 0:
            return description
        assert description.topic is not None
        if mulitport:
            return PrismBinarySensorEntityDescription(
                key=description.key.format(port),
                topic=description.topic.format(port),
                entity_category=description.entity_category,
                device_class=description.device_class,
                has_entity_name=description.has_entity_name,
                translation_key=description.translation_key,
                expire_after=description.expire_after,
            )
        return PrismBinarySensorEntityDescription(
            key=description.key[:-3],
            topic=description.topic.format(port),
            entity_category=description.entity_category,
            device_class=description.device_class,
            has_entity_name=description.has_entity_name,
            translation_key=description.translation_key,
            expire_after=description.expire_after,
        )

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        description: PrismBinarySensorEntityDescription,
        port: int,
    ) -> None:
        """Init Prism error binary sensor."""
        ismultiport = entry_data.ports > 1
        super().__init__(
            entry_data, self._get_description(port, ismultiport, description), port
        )

    @override
    def _message_received(self, msg) -> None:
        """Update the error sensor with the most recent event."""
        self.schedule_expiration_callback()

        try:
            error_value = int(msg.payload)
            # OFF when value is 0, ON when different from 0
            self._attr_is_on = error_value != 0
        except ValueError, TypeError:
            # If we can't parse the value, assume there's an error
            self._attr_is_on = True

        self.schedule_update_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to mqtt."""
        await super().async_added_to_hass()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from mqtt."""
        _LOGGER.debug("async_will_remove_from_hass")
        await super().async_will_remove_from_hass()
        self.cleanup_expiration_trigger()


class PrismEventBinarySensor(PrismBinarySensor):
    """Prism button event sensor entity."""

    _attr_has_entity_name = True

    entity_description: PrismEventBinarySensorEntityDescription

    def _get_description(
        self,
        port: int,
        mulitport: bool,
        description: PrismEventBinarySensorEntityDescription,
    ) -> PrismEventBinarySensorEntityDescription:
        if port == 0:
            return description
        assert description.topic is not None
        if mulitport:
            return PrismEventBinarySensorEntityDescription(
                key=description.key.format(port),
                topic=description.topic.format(port),
                entity_category=description.entity_category,
                device_class=description.device_class,
                has_entity_name=description.has_entity_name,
                sequence=description.sequence,
                accepted_sequences=description.accepted_sequences,
                translation_key=description.translation_key,
                expire_after=description.expire_after,
            )
        return PrismEventBinarySensorEntityDescription(
            key=description.key[:-3],
            topic=description.topic.format(port),
            entity_category=description.entity_category,
            device_class=description.device_class,
            has_entity_name=description.has_entity_name,
            sequence=description.sequence,
            accepted_sequences=description.accepted_sequences,
            translation_key=description.translation_key,
            expire_after=description.expire_after,
        )

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        description: PrismEventBinarySensorEntityDescription,
        port: int,
    ) -> None:
        """Init Prism event binary sensor."""
        ismultiport = entry_data.ports > 1
        super().__init__(
            entry_data, self._get_description(port, ismultiport, description), port
        )
        self._accepted_sequences = description.accepted_sequences or (
            description.sequence,
        )

    @override
    def _message_received(self, msg) -> None:
        """Update the sensor with the most recent event."""
        self.schedule_expiration_callback()

        sequence = normalize_touch_payload(msg.payload)
        if sequence not in self._accepted_sequences:
            _LOGGER.debug(
                "Ignoring touch payload %r parsed as %s for topic %s; expected %s",
                msg.payload,
                sequence,
                self._topic,
                self._accepted_sequences,
            )
            return

        if self._expiration_trigger:
            self._expiration_trigger()
        self._attr_is_on = True
        self._expiration_trigger = async_call_later(self.hass, 2.0, self._restore_value)
        self.schedule_update_ha_state()

    @callback
    def _restore_value(self, *_: datetime) -> None:
        """Triggered when value is expired."""
        _LOGGER.debug("entity _value_is_expired for topic %s", self._topic)
        self._expiration_trigger = None
        self._attr_is_on = False
        self.async_write_ha_state()


BASE_BINARYSENSORS = [
    PrismBinarySensorEntityDescription(
        key="online",
        topic="1/volt",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        has_entity_name=True,
        translation_key="online",
        expire_after=150,
    ),
]

ERROR_BINARYSENSORS = [
    PrismBinarySensorEntityDescription(
        key="error_{}",
        topic="{}/error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        has_entity_name=True,
        translation_key="error",
    ),
]

EVENTS_BINARYSENSORS = [
    PrismEventBinarySensorEntityDescription(
        key="touch_single_{}",
        topic="{}/input/touch",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.MOTION,
        has_entity_name=True,
        sequence=(1,),
        accepted_sequences=((1,),),
        translation_key="touch_single",
        expire_after=0,
    ),
    PrismEventBinarySensorEntityDescription(
        key="touch_double_{}",
        topic="{}/input/touch",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.MOTION,
        has_entity_name=True,
        sequence=(
            1,
            1,
        ),
        accepted_sequences=((1, 1), (2,)),
        translation_key="touch_double",
        expire_after=0,
    ),
    PrismEventBinarySensorEntityDescription(
        key="touch_long_{}",
        topic="{}/input/touch",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.MOTION,
        has_entity_name=True,
        sequence=(3,),
        accepted_sequences=((3,),),
        translation_key="touch_long",
        expire_after=0,
    ),
]
