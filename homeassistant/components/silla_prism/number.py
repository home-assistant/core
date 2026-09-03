"""Contains numbers configurations for Prism wallbox integration."""

import logging
from typing import override

from homeassistant.components import mqtt
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import NUMBER_DOMAIN
from .entity import PrismBaseEntity
from .entry_data import RuntimeEntryData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    entry_data: RuntimeEntryData = entry.runtime_data
    _LOGGER.debug("async_setup_entry for numbers: %s", entry_data)

    ports = entry_data.ports

    numbers = []
    for port in range(1, ports + 1):
        numbers.extend(
            [PrismNumber(entry_data, description, port) for description in NUMBERS]
        )

    async_add_entities(numbers)


class PrismNumberEntityDescription(NumberEntityDescription, frozen_or_thawed=True):
    """A class that describes prism binary sensor entities."""

    expire_after: float = 0
    topic: str | None = None
    topic_out: str | None = None


class PrismNumber(PrismBaseEntity, NumberEntity):
    """Prism number entity."""

    _attr_has_entity_name = True

    entity_description: PrismNumberEntityDescription

    def description(
        self,
        port: int,
        mulitport: bool,
        max_current: int,
        description: PrismNumberEntityDescription,
    ) -> PrismNumberEntityDescription:
        """Create a Number entity for Prism EVSE devices."""
        assert description.topic is not None
        assert description.topic_out is not None
        if mulitport:
            return PrismNumberEntityDescription(
                key=description.key.format(port),
                topic=description.topic.format(port),
                topic_out=description.topic_out.format(port),
                entity_category=description.entity_category,
                device_class=description.device_class,
                native_min_value=description.native_min_value,
                native_max_value=max_current,
                native_step=description.native_step,
                mode=description.mode,
                has_entity_name=description.has_entity_name,
                translation_key=description.translation_key,
            )
        return PrismNumberEntityDescription(
            key=description.key[:-3],
            topic=description.topic.format(port),
            topic_out=description.topic_out.format(port),
            entity_category=description.entity_category,
            device_class=description.device_class,
            native_min_value=description.native_min_value,
            native_max_value=max_current,
            native_step=description.native_step,
            mode=description.mode,
            has_entity_name=description.has_entity_name,
            translation_key=description.translation_key,
        )

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        description: PrismNumberEntityDescription,
        port: int,
    ) -> None:
        """Init Prism select."""
        max_current = entry_data.maxcurr
        ismultiport = entry_data.ports > 1
        if not ismultiport:
            device = entry_data.devices[0]
        else:
            device = entry_data.devices[port]

        self._entry_data = entry_data
        self._port = port
        _description = self.description(port, ismultiport, max_current, description)
        super().__init__(
            entry_data,
            NUMBER_DOMAIN,
            _description,
            device,
        )

        self._topic_out = (
            entry_data.topic + _description.topic_out
            if _description.topic_out
            else None
        )
        self._attr_native_value = self.native_min_value

    @override
    def _message_received(self, msg) -> None:
        """Update the sensor with the most recent event."""
        self._attr_native_value = msg.payload
        self.schedule_update_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to mqtt."""
        if self.entity_description.topic:
            await self._subscribe_topic()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from mqtt."""
        _LOGGER.debug("async_will_remove_from_hass key:%s", self.entity_description.key)
        await super().async_will_remove_from_hass()
        self.cleanup_expiration_trigger()

    @override
    def set_native_value(self, _: float) -> None:
        """Set the native value."""
        raise NotImplementedError

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        # _LOGGER.debug(
        #     "async_set_native_value key:%s topic:%s value:%f",
        #     self.entity_description.key,
        #     self._topic_out,
        #     value,
        # )
        int_value = int(value)
        if self._topic_out is not None:
            await mqtt.async_publish(self.hass, self._topic_out, int_value)


NUMBERS: tuple[PrismNumberEntityDescription, ...] = (
    PrismNumberEntityDescription(
        key="set_max_current_{}",
        topic="{}/user_amp",
        topic_out="{}/command/set_current_user",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=6,
        native_max_value=16,
        mode=NumberMode.BOX,
        has_entity_name=True,
        translation_key="set_max_current",
    ),
    PrismNumberEntityDescription(
        key="set_current_limit_{}",
        topic="{}/pilot",
        topic_out="{}/command/set_current_limit",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=6,
        native_max_value=16,
        has_entity_name=True,
        translation_key="set_current_limit",
    ),
)
