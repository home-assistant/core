"""Support for Vallox ventilation unit selects."""
from __future__ import annotations

from dataclasses import dataclass

from vallox_websocket_api import Vallox

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ValloxDataUpdateCoordinator, ValloxEntity
from .const import DOMAIN


class ValloxNumber(ValloxEntity, NumberEntity):
    """Representation of a Vallox sensor."""

    entity_description: ValloxNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxNumberEntityDescription,
        client: Vallox,
    ) -> None:
        """Initialize the Vallox sensor."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"
        self._client = client

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor."""
        if (metric_key := self.entity_description.metric_key) is None:
            return None

        if (value := self.coordinator.data.get_metric(metric_key)) is None:
            return None

        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if (metric_key := self.entity_description.metric_key) is None:
            return
        self._attr_native_value = value
        await self._client.set_values({metric_key: float(value)})
        await self.coordinator.async_request_refresh()


@dataclass
class ValloxNumberEntityDescription(NumberEntityDescription):
    """Describes Vallox select entity."""

    metric_key: str | None = None
    sensor_type: type[ValloxNumber] = ValloxNumber


NUMBER_TYPES: tuple[ValloxNumberEntityDescription, ...] = (
    ValloxNumberEntityDescription(
        key="supply_air_target_home",
        name="Supply air temperature (Home)",
        metric_key="A_CYC_HOME_AIR_TEMP_TARGET",
        sensor_type=ValloxNumber,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
    ),
    ValloxNumberEntityDescription(
        key="supply_air_target_away",
        name="Supply air temperature (Away)",
        metric_key="A_CYC_AWAY_AIR_TEMP_TARGET",
        sensor_type=ValloxNumber,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
    ),
    ValloxNumberEntityDescription(
        key="fan_speed_home",
        name="Fan speed (Home)",
        metric_key="A_CYC_HOME_SPEED_SETTING",
        sensor_type=ValloxNumber,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
    ),
    ValloxNumberEntityDescription(
        key="fan_speed_away",
        name="Fan speed (Away)",
        metric_key="A_CYC_AWAY_SPEED_SETTING",
        sensor_type=ValloxNumber,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
    ),
    ValloxNumberEntityDescription(
        key="fan_speed_boost",
        name="Fan speed (Boost)",
        metric_key="A_CYC_BOOST_SPEED_SETTING",
        sensor_type=ValloxNumber,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]

    async_add_entities(
        [
            description.sensor_type(name, coordinator, description, client)
            for description in NUMBER_TYPES
        ]
    )
