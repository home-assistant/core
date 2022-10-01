"""Support for WiZ sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import POWER_WATT, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WizEntity
from .models import WizData

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="rssi",
        name="Signal strength",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
)


POWER_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="power",
        name="Current power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_WATT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the wiz sensor."""
    wiz_data: WizData = hass.data[DOMAIN][entry.entry_id]
    entities = [
        WizSensor(wiz_data, entry.title, description) for description in SENSORS
    ]
    if wiz_data.coordinator.data is not None:
        entities.extend(
            [
                WizPowerSensor(wiz_data, entry.title, description)
                for description in POWER_SENSORS
            ]
        )
    async_add_entities(entities)


class WizSensor(WizEntity, SensorEntity):
    """Defines a WiZ sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self, wiz_data: WizData, name: str, description: SensorEntityDescription
    ) -> None:
        """Initialize an WiZ sensor."""
        super().__init__(wiz_data, name)
        self.entity_description = description
        self._attr_unique_id = f"{self._device.mac}_{description.key}"
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = self._device.state.pilotResult.get(
            self.entity_description.key
        )


class WizPowerSensor(WizSensor):
    """Defines a WiZ power sensor."""

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        # Newer firmwares will have the power in their state
        watts_push = self._device.state.get_power()
        # Older firmwares will be polled and in the coordinator data
        watts_poll = self.coordinator.data
        self._attr_native_value = watts_poll if watts_push is None else watts_push
