"""Support for configuring different deCONZ sensors."""

from __future__ import annotations

from dataclasses import dataclass

from pydeconz.sensor import Presence

from homeassistant.components.number import (
    DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


@dataclass
class DeconzNumberEntityDescription(NumberEntityDescription):
    """Class describing deCONZ number entities."""

    entity_category = "config"
    attribute: str | None = None
    suffix: str | None = None
    update_key: str | None = None
    max_value: int | None = None
    min_value: int | None = None
    step: int | None = None


ENTITY_DESCRIPTIONS = {
    Presence: [
        DeconzNumberEntityDescription(
            key="duration",
            attribute="duration",
            suffix="Duration",
            update_key="duration",
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
            for description in ENTITY_DESCRIPTIONS.get(sensor.__class__, []):
                if getattr(sensor, description.attribute) is None:
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
    """Representation of a deCONZ number config entity."""

    TYPE = DOMAIN

    def __init__(self, device, gateway, description):
        """Initialize deCONZ binary sensor."""
        super().__init__(device, gateway)

        self.entity_description = description

        self._attr_name = f"{self._device.name} {description.suffix}"
        self._attr_unique_id = f"{self.serial}-{self.entity_description.suffix.lower()}"
        self._attr_max_value = self.entity_description.max_value
        self._attr_min_value = self.entity_description.min_value
        self._attr_step = self.entity_description.step

    @callback
    def async_update_callback(self, force_update: bool = False) -> None:
        """Update the number value."""
        keys = {self.entity_description.update_key, "reachable"}
        if force_update or self._device.changed_keys.intersection(keys):
            super().async_update_callback(force_update=force_update)

    @property
    def value(self) -> float:
        """Return the value of the sensor attribute."""
        return getattr(self._device, self.entity_description.attribute)

    async def async_set_value(self, value: float) -> None:
        """Set sensor config."""
        data = {self.entity_description.attribute: int(value)}
        await self._device.set_config(**data)
