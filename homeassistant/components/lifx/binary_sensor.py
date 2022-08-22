"""Binary sensor entities for LIFX integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    HEV_CYCLE_DURATION,
    HEV_CYCLE_LAST_POWER,
    HEV_CYCLE_LAST_RESULT,
    HEV_CYCLE_REMAINING,
    HEV_CYCLE_STATUS,
)
from .coordinator import LIFXSensorUpdateCoordinator
from .entity import LIFXEntity
from .models import LIFXCoordination
from .util import lifx_features


@dataclass
class LIFXBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes LIFX binary sensor entities."""

    attributes: dict[str, str] | None = None


HEV_CYCLE_STATUS_SENSOR = LIFXBinarySensorEntityDescription(
    key=HEV_CYCLE_STATUS,
    name="Clean Cycle",
    entity_category=EntityCategory.DIAGNOSTIC,
    device_class=BinarySensorDeviceClass.RUNNING,
    attributes={
        "total_duration": HEV_CYCLE_DURATION,
        "restore_power": HEV_CYCLE_LAST_POWER,
        "time_remaining": HEV_CYCLE_REMAINING,
        "last_result": HEV_CYCLE_LAST_RESULT,
    },
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LIFX from a config entry."""
    lifx_coordination: LIFXCoordination = hass.data[DOMAIN][entry.entry_id]
    coordinator: LIFXSensorUpdateCoordinator = lifx_coordination.sensor_coordinator

    if lifx_features(coordinator.device)["hev"]:
        async_add_entities(
            [
                LIFXBinarySensorEntity(
                    coordinator=coordinator, description=HEV_CYCLE_STATUS_SENSOR
                )
            ]
        )


class LIFXBinarySensorEntity(LIFXEntity, BinarySensorEntity):
    """LIFX sensor entity base class."""

    _attr_has_entity_name: bool = True
    coordinator: LIFXSensorUpdateCoordinator
    entity_description: LIFXBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: LIFXSensorUpdateCoordinator,
        description: LIFXBinarySensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        self._attr_is_on = self.coordinator.get_hev_cycle_status()
        if self.entity_description.attributes:
            self._attr_extra_state_attributes = {
                key: self.coordinator.async_get_extra_state_attribute(val)
                for key, val in self.entity_description.attributes.items()
            }

    @callback
    async def async_added_to_hass(self) -> None:
        """Enable update of sensor data."""
        self.async_on_remove(
            self.coordinator.async_enable_sensor(self.entity_description.key)
        )
        await super().async_added_to_hass()
