"""Support for Vallox ventilation unit numbers."""
from __future__ import annotations

from dataclasses import dataclass

from vallox_websocket_api import Vallox

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ValloxDataUpdateCoordinator, ValloxEntity
from .const import DOMAIN


class ValloxNumberEntity(ValloxEntity, NumberEntity):
    """Representation of a Vallox number entity."""

    entity_description: ValloxNumberEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxNumberEntityDescription,
        client: Vallox,
    ) -> None:
        """Initialize the Vallox number entity."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"
        self._client = client

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor."""
        if (
            value := self.coordinator.data.get_metric(
                self.entity_description.metric_key
            )
        ) is None:
            return None

        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._client.set_values(
            {self.entity_description.metric_key: float(value)}
        )
        await self.coordinator.async_request_refresh()


@dataclass
class ValloxMetricMixin:
    """Holds Vallox metric key."""

    metric_key: str


@dataclass
class ValloxNumberEntityDescription(NumberEntityDescription, ValloxMetricMixin):
    """Describes Vallox number entity."""


NUMBER_ENTITIES: tuple[ValloxNumberEntityDescription, ...] = (
    ValloxNumberEntityDescription(
        key="supply_air_target_home",
        translation_key="supply_air_target_home",
        metric_key="A_CYC_HOME_AIR_TEMP_TARGET",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
    ),
    ValloxNumberEntityDescription(
        key="supply_air_target_away",
        translation_key="supply_air_target_away",
        metric_key="A_CYC_AWAY_AIR_TEMP_TARGET",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
    ),
    ValloxNumberEntityDescription(
        key="supply_air_target_boost",
        translation_key="supply_air_target_boost",
        metric_key="A_CYC_BOOST_AIR_TEMP_TARGET",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ValloxNumberEntity(
                data["name"], data["coordinator"], description, data["client"]
            )
            for description in NUMBER_ENTITIES
        ]
    )
