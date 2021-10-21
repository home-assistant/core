"""Support for configuring different deCONZ sensors."""

from __future__ import annotations

from dataclasses import dataclass

from pydeconz.sensor import PRESENCE_DELAY, Presence

from homeassistant.components.number import (
    DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


@dataclass
class DeconzNumberEntityDescription(NumberEntityDescription):
    """Class describing deCONZ number entities."""

    entity_category = ENTITY_CATEGORY_CONFIG
    device_property: str | None = None
    suffix: str | None = None
    update_key: str | None = None
    max_value: int | None = None
    min_value: int | None = None
    step: int | None = None


ENTITY_DESCRIPTIONS = {
    Presence: [
        DeconzNumberEntityDescription(
            key="delay",
            device_property="delay",
            suffix="Delay",
            update_key=PRESENCE_DELAY,
            max_value=65535,
            min_value=0,
            step=1,
        )
    ]
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ number entity."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_sensor(sensors=gateway.api.sensors.values()):
        """Add number config sensor from deCONZ."""
        entities = []

        for sensor in sensors:

            if sensor.type.startswith("CLIP"):
                continue

            known_number_entities = set(gateway.entities[DOMAIN])
            for description in ENTITY_DESCRIPTIONS.get(type(sensor), []):

                if getattr(sensor, description.device_property) is None:
                    continue

                new_number_entity = DeconzNumber(sensor, gateway, description)
                if new_number_entity.unique_id not in known_number_entities:
                    entities.append(new_number_entity)

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

    def __init__(self, device, gateway, description):
        """Initialize deCONZ number entity."""
        self.entity_description = description
        super().__init__(device, gateway)

        self._attr_name = f"{self._device.name} {description.suffix}"
        self._attr_max_value = description.max_value
        self._attr_min_value = description.min_value
        self._attr_step = description.step

    @callback
    def async_update_callback(self) -> None:
        """Update the number value."""
        keys = {self.entity_description.update_key, "reachable"}
        if self._device.changed_keys.intersection(keys):
            super().async_update_callback()

    @property
    def value(self) -> float:
        """Return the value of the sensor property."""
        return getattr(self._device, self.entity_description.device_property)

    async def async_set_value(self, value: float) -> None:
        """Set sensor config."""
        data = {self.entity_description.device_property: int(value)}
        await self._device.set_config(**data)

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return f"{self.serial}-{self.entity_description.suffix.lower()}"
