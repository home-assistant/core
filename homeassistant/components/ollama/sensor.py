"""Sensor platform for the Ollama integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

import ollama

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OllamaConfigEntry
from .const import DOMAIN
from .coordinator import OllamaData, OllamaDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class OllamaSensorEntityDescription(SensorEntityDescription):
    """Describe an Ollama sensor entity."""

    value_fn: Callable[[OllamaData], int]
    attr_fn: Callable[[OllamaData], dict[str, list[str]] | None] = lambda _: None
    available_fn: Callable[[OllamaData], bool] = lambda _: True


def _loaded_models(data: OllamaData) -> ollama.ProcessResponse:
    """Return loaded model data."""
    assert data.loaded is not None
    return data.loaded


SENSORS: tuple[OllamaSensorEntityDescription, ...] = (
    OllamaSensorEntityDescription(
        key="loaded_models",
        translation_key="loaded_models",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: len(_loaded_models(data).models),
        attr_fn=lambda data: {
            "names": sorted(
                model.model for model in _loaded_models(data).models if model.model
            )
        },
        available_fn=lambda data: data.loaded is not None,
    ),
    OllamaSensorEntityDescription(
        key="installed_models",
        translation_key="installed_models",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: len(data.installed.models),
        attr_fn=lambda data: {
            "names": sorted(
                model.model for model in data.installed.models if model.model
            )
        },
        available_fn=lambda data: data.installed is not None,
    ),
    OllamaSensorEntityDescription(
        key="loaded_model_size",
        translation_key="loaded_model_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: sum(
            model.size or 0 for model in _loaded_models(data).models
        ),
        available_fn=lambda data: data.loaded is not None,
    ),
    OllamaSensorEntityDescription(
        key="loaded_model_gpu_memory",
        translation_key="loaded_model_gpu_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: sum(
            model.size_vram or 0 for model in _loaded_models(data).models
        ),
        available_fn=lambda data: data.loaded is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OllamaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ollama sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [OllamaModelsSensor(entry, coordinator, description) for description in SENSORS]
    )


class OllamaModelsSensor(CoordinatorEntity[OllamaDataUpdateCoordinator], SensorEntity):
    """Ollama sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    entity_description: OllamaSensorEntityDescription

    def __init__(
        self,
        entry: OllamaConfigEntry,
        coordinator: OllamaDataUpdateCoordinator,
        description: OllamaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Ollama",
            model="Ollama",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the sensor is available."""
        return (
            super().available
            and (data := self.coordinator.data) is not None
            and self.entity_description.available_fn(data)
        )

    @property
    @override
    def native_value(self) -> int | None:
        """Return the sensor value."""
        if (data := self.coordinator.data) is None or not (
            self.entity_description.available_fn(data)
        ):
            return None
        return self.entity_description.value_fn(data)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, list[str]] | None:
        """Return the model names."""
        if (data := self.coordinator.data) is None or not (
            self.entity_description.available_fn(data)
        ):
            return None
        return self.entity_description.attr_fn(data)
