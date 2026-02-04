"""Support for Helios ventilation unit numbers."""

from __future__ import annotations

from dataclasses import dataclass

from helios_websocket_api import Helios

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeliosConfigEntry
from .coordinator import HeliosDataUpdateCoordinator
from .entity import HeliosEntity


class HeliosNumberEntity(HeliosEntity, NumberEntity):
    """Representation of a Helios number entity."""

    entity_description: HeliosNumberEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HeliosDataUpdateCoordinator,
        description: HeliosNumberEntityDescription,
        client: Helios,
    ) -> None:
        """Initialize the Helios number entity."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"
        self._client = client

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor."""
        if (
            value := self.coordinator.data.get(self.entity_description.metric_key)
        ) is None:
            return None

        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._client.set_values(
            {self.entity_description.metric_key: float(value)}
        )
        await self.coordinator.async_request_refresh()


@dataclass(frozen=True, kw_only=True)
class HeliosNumberEntityDescription(NumberEntityDescription):
    """Describes Helios number entity."""

    metric_key: str


NUMBER_ENTITIES: tuple[HeliosNumberEntityDescription, ...] = (
    HeliosNumberEntityDescription(
        key="supply_air_target_home",
        translation_key="supply_air_target_home",
        metric_key="A_CYC_HOME_AIR_TEMP_TARGET",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
    ),
    HeliosNumberEntityDescription(
        key="supply_air_target_away",
        translation_key="supply_air_target_away",
        metric_key="A_CYC_AWAY_AIR_TEMP_TARGET",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
    ),
    HeliosNumberEntityDescription(
        key="supply_air_target_boost",
        translation_key="supply_air_target_boost",
        metric_key="A_CYC_BOOST_AIR_TEMP_TARGET",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    client = coordinator.client

    async_add_entities(
        HeliosNumberEntity(coordinator, description, client)
        for description in NUMBER_ENTITIES
    )
