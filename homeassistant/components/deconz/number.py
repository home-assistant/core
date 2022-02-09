"""Support for configuring different deCONZ sensors."""

from __future__ import annotations

from collections.abc import Callable, ValuesView
from dataclasses import dataclass

from pydeconz.sensor import PRESENCE_DELAY, DeconzSensor as PydeconzSensor, Presence

from homeassistant.components.number import (
    DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry


@dataclass
class DeconzNumberDescriptionMixin:
    """Required values when describing deCONZ number entities."""

    suffix: str
    update_key: str
    value_fn: Callable[[PydeconzSensor], bool | None]


@dataclass
class DeconzNumberDescription(NumberEntityDescription, DeconzNumberDescriptionMixin):
    """Class describing deCONZ number entities."""


ENTITY_DESCRIPTIONS = {
    Presence: [
        DeconzNumberDescription(
            key="delay",
            value_fn=lambda device: device.delay,
            suffix="Delay",
            update_key=PRESENCE_DELAY,
            max_value=65535,
            min_value=0,
            step=1,
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
    def async_add_sensor(
        sensors: list[Presence] | ValuesView[Presence] = gateway.api.sensors.values(),
    ) -> None:
        """Add number config sensor from deCONZ."""
        entities = []

        for sensor in sensors:

            if sensor.type.startswith("CLIP"):
                continue

            known_entities = set(gateway.entities[DOMAIN])
            for description in ENTITY_DESCRIPTIONS.get(type(sensor), []):

                if (
                    not hasattr(sensor, description.key)
                    or description.value_fn(sensor) is None
                ):
                    continue

                new_entity = DeconzNumber(sensor, gateway, description)
                if new_entity.unique_id not in known_entities:
                    entities.append(new_entity)

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_new_sensor,
            async_add_sensor,
        )
    )

    async_add_sensor(
        [gateway.api.sensors[key] for key in sorted(gateway.api.sensors, key=int)]
    )


class DeconzNumber(DeconzDevice, NumberEntity):
    """Representation of a deCONZ number entity."""

    TYPE = DOMAIN
    _device: Presence

    def __init__(
        self,
        device: Presence,
        gateway: DeconzGateway,
        description: DeconzNumberDescription,
    ) -> None:
        """Initialize deCONZ number entity."""
        self.entity_description: DeconzNumberDescription = description
        super().__init__(device, gateway)

        self._attr_name = f"{device.name} {description.suffix}"
        self._update_keys = {self.entity_description.update_key, "reachable"}

    @callback
    def async_update_callback(self) -> None:
        """Update the number value."""
        if self._device.changed_keys.intersection(self._update_keys):
            super().async_update_callback()

    @property
    def value(self) -> float:
        """Return the value of the sensor property."""
        return self.entity_description.value_fn(self._device)  # type: ignore[no-any-return]

    async def async_set_value(self, value: float) -> None:
        """Set sensor config."""
        data = {self.entity_description.key: int(value)}
        await self._device.set_config(**data)

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return f"{self.serial}-{self.entity_description.suffix.lower()}"
