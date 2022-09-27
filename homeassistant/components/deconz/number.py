"""Support for configuring different deCONZ sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydeconz.models.event import EventType
from pydeconz.models.sensor.presence import Presence

from homeassistant.components.number import (
    DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry


@dataclass
class DeconzNumberDescriptionMixin:
    """Required values when describing deCONZ number entities."""

    suffix: str
    update_key: str
    value_fn: Callable[[Presence], float | None]


@dataclass
class DeconzNumberDescription(NumberEntityDescription, DeconzNumberDescriptionMixin):
    """Class describing deCONZ number entities."""


ENTITY_DESCRIPTIONS = {
    Presence: [
        DeconzNumberDescription(
            key="delay",
            value_fn=lambda device: device.delay,
            suffix="Delay",
            update_key="delay",
            native_max_value=65535,
            native_min_value=0,
            native_step=1,
            entity_category=EntityCategory.CONFIG,
        )
    ]
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ number entity."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_sensor(_: EventType, sensor_id: str) -> None:
        """Add sensor from deCONZ."""
        sensor = gateway.api.sensors.presence[sensor_id]

        for description in ENTITY_DESCRIPTIONS.get(type(sensor), []):
            if (
                not hasattr(sensor, description.key)
                or description.value_fn(sensor) is None
            ):
                continue
            async_add_entities([DeconzNumber(sensor, gateway, description)])

    gateway.register_platform_add_device_callback(
        async_add_sensor,
        gateway.api.sensors.presence,
        always_ignore_clip_sensors=True,
    )


class DeconzNumber(DeconzDevice[Presence], NumberEntity):
    """Representation of a deCONZ number entity."""

    TYPE = DOMAIN

    def __init__(
        self,
        device: Presence,
        gateway: DeconzGateway,
        description: DeconzNumberDescription,
    ) -> None:
        """Initialize deCONZ number entity."""
        self.entity_description: DeconzNumberDescription = description
        self._update_key = self.entity_description.update_key
        self._name_suffix = description.suffix
        super().__init__(device, gateway)

    @property
    def native_value(self) -> float | None:
        """Return the value of the sensor property."""
        return self.entity_description.value_fn(self._device)

    async def async_set_native_value(self, value: float) -> None:
        """Set sensor config."""
        await self.gateway.api.sensors.presence.set_config(
            id=self._device.resource_id,
            delay=int(value),
        )

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return f"{self.serial}-{self.entity_description.suffix.lower()}"
