"""Sensor platform for Sun integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SIGNAL_EVENTS_CHANGED
from .entity import Sun, SunConfigEntry

ENTITY_ID_BINARY_SENSOR_FORMAT = BINARY_SENSOR_DOMAIN + ".sun_{}"


@dataclass(kw_only=True, frozen=True)
class SunBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Sun sensor entity."""

    value_fn: Callable[[Sun], bool | None]
    signal: str


BINARY_SENSOR_TYPES: tuple[SunBinarySensorEntityDescription, ...] = (
    SunBinarySensorEntityDescription(
        key="solar_rising",
        translation_key="solar_rising",
        value_fn=lambda data: data.rising,
        entity_registry_enabled_default=False,
        signal=SIGNAL_EVENTS_CHANGED,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sun binary sensor platform."""

    sun = entry.runtime_data

    async_add_entities(
        [
            SunBinarySensor(sun, description, entry.entry_id)
            for description in BINARY_SENSOR_TYPES
        ]
    )


class SunBinarySensor(BinarySensorEntity):
    """Representation of a Sun Sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: SunBinarySensorEntityDescription

    def __init__(
        self,
        sun: Sun,
        entity_description: SunBinarySensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initiate Sun Binary Sensor."""
        self.entity_description = entity_description
        self.entity_id = ENTITY_ID_BINARY_SENSOR_FORMAT.format(entity_description.key)
        self._attr_unique_id = f"{entry_id}-binary-{entity_description.key}"
        self.sun = sun
        self._attr_device_info = DeviceInfo(
            name="Sun",
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool | None:
        """Return value of binary sensor."""
        return self.entity_description.value_fn(self.sun)

    async def async_added_to_hass(self) -> None:
        """Register signal listener when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.entity_description.signal,
                self.async_write_ha_state,
            )
        )
