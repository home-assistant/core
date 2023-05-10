"""Support for configuring different deCONZ numbers."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydeconz.gateway import DeconzSession
from pydeconz.interfaces.sensors import SensorResources
from pydeconz.models.event import EventType
from pydeconz.models.sensor import SensorBase as PydeconzSensorBase
from pydeconz.models.sensor.presence import Presence

from homeassistant.components.number import (
    DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er

from .const import DOMAIN as DECONZ_DOMAIN
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry
from .util import serial_from_unique_id

T = TypeVar("T", Presence, PydeconzSensorBase)


@dataclass
class DeconzNumberDescriptionMixin(Generic[T]):
    """Required values when describing deCONZ number entities."""

    instance_check: type[T]
    name_suffix: str
    set_fn: Callable[[DeconzSession, str, int], Coroutine[Any, Any, dict[str, Any]]]
    update_key: str
    value_fn: Callable[[T], float | None]


@dataclass
class DeconzNumberDescription(NumberEntityDescription, DeconzNumberDescriptionMixin[T]):
    """Class describing deCONZ number entities."""


ENTITY_DESCRIPTIONS: tuple[DeconzNumberDescription, ...] = (
    DeconzNumberDescription[Presence](
        key="delay",
        instance_check=Presence,
        name_suffix="Delay",
        set_fn=lambda api, id, v: api.sensors.presence.set_config(id=id, delay=v),
        update_key="delay",
        value_fn=lambda device: device.delay,
        native_max_value=65535,
        native_min_value=0,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    DeconzNumberDescription[Presence](
        key="duration",
        instance_check=Presence,
        name_suffix="Duration",
        set_fn=lambda api, id, v: api.sensors.presence.set_config(id=id, duration=v),
        update_key="duration",
        value_fn=lambda device: device.duration,
        native_max_value=65535,
        native_min_value=0,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
)


@callback
def async_update_unique_id(
    hass: HomeAssistant, unique_id: str, description: DeconzNumberDescription
) -> None:
    """Update unique ID base to be on full unique ID rather than device serial.

    Introduced with release 2022.11.
    """
    ent_reg = er.async_get(hass)

    new_unique_id = f"{unique_id}-{description.key}"
    if ent_reg.async_get_entity_id(DOMAIN, DECONZ_DOMAIN, new_unique_id):
        return

    unique_id = f"{serial_from_unique_id(unique_id)}-{description.key}"
    if entity_id := ent_reg.async_get_entity_id(DOMAIN, DECONZ_DOMAIN, unique_id):
        ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)


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

        for description in ENTITY_DESCRIPTIONS:
            if (
                not isinstance(sensor, description.instance_check)
                or description.value_fn(sensor) is None
            ):
                continue
            if description.key == "delay":
                async_update_unique_id(hass, sensor.unique_id, description)
            async_add_entities([DeconzNumber(sensor, gateway, description)])

    gateway.register_platform_add_device_callback(
        async_add_sensor,
        gateway.api.sensors.presence,
        always_ignore_clip_sensors=True,
    )


class DeconzNumber(DeconzDevice[SensorResources], NumberEntity):
    """Representation of a deCONZ number entity."""

    TYPE = DOMAIN
    entity_description: DeconzNumberDescription

    def __init__(
        self,
        device: SensorResources,
        gateway: DeconzGateway,
        description: DeconzNumberDescription,
    ) -> None:
        """Initialize deCONZ number entity."""
        self.entity_description = description
        self.unique_id_suffix = description.key
        self._name_suffix = description.name_suffix
        self._update_key = description.update_key
        super().__init__(device, gateway)

    @property
    def native_value(self) -> float | None:
        """Return the value of the sensor property."""
        return self.entity_description.value_fn(self._device)

    async def async_set_native_value(self, value: float) -> None:
        """Set sensor config."""
        await self.entity_description.set_fn(
            self.gateway.api,
            self._device.resource_id,
            int(value),
        )
