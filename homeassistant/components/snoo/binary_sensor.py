"""Support for Snoo Binary Sensors."""

# from __future__ import annotations

# from collections.abc import Callable
# from dataclasses import dataclass

# from python_snoo.containers import SnooData

# from homeassistant.components.binary_sensor import (
#     BinarySensorDeviceClass,
#     BinarySensorEntity,
#     BinarySensorEntityDescription,
# )
# from homeassistant.const import UnitOfTemperature, UnitOfTime
# from homeassistant.core import HomeAssistant
# from homeassistant.helpers.entity_platform import AddEntitiesCallback
# from homeassistant.helpers.typing import StateType

# from . import SnooConfigEntry
# from .coordinator import SnooCoordinator
# from .entity import SnooDescriptionEntity


# @dataclass(frozen=True, kw_only=True)
# class SnooBinarySensorEntityDescription(BinarySensorEntityDescription):
#     """Describes a Snoo binary sensor."""

#     value_fn: Callable[[SnooData], bool]


# BINARY_SENSOR_DESCRIPTIONS: list[SnooBinarySensorEntityDescription] = [
#     SnooBinarySensorEntityDescription(
#         key="left_clip",
#         translation_key="left_clip",
#         value_fn=lambda data: data.left_safety_clip,
#         device_class=BinarySensorDeviceClass.CONNECTIVITY,
#     ),
#     SnooBinarySensorEntityDescription(
#         key="right_clip",
#         translation_key="right_clip",
#         value_fn=lambda data: data.right_safety_clip,
#         device_class=BinarySensorDeviceClass.CONNECTIVITY,
#     ),
# ]


# async def async_setup_entry(
#     hass: HomeAssistant,
#     entry: SnooConfigEntry,
#     async_add_entities: AddEntitiesCallback,
# ) -> None:
#     """Set up Snoo device."""
#     coordinators: dict[str, SnooCoordinator] = entry.runtime_data
#     entities = []
#     for coordinator in coordinators.values():
#         for description in BINARY_SENSOR_DESCRIPTIONS:
#             entities.append(SnooBinarySensor(coordinator, description))
#     async_add_entities(entities)


# class SnooBinarySensor(SnooDescriptionEntity, BinarySensorEntity):
#     """A sensor using Snoo coordinator."""

#     entity_description: SnooBinarySensorEntityDescription

#     @property
#     def is_on(self) -> bool:
#         """Return the value reported by the sensor."""
#         return bool(self.entity_description.value_fn(self.coordinator.data))
