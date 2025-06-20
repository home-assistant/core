"""Support for Droplet."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_NAME,
    CONF_MODEL,
    DOMAIN,
    KEY_CURRENT_FLOW_RATE,
    NAME_CURRENT_FLOW_RATE,
)
from .coordinator import DropletConfigEntry, DropletDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DropletConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Droplet sensors from config entry."""
    _LOGGER.info(
        "Set up sensor for device %s with entry_id is %s",
        config_entry.unique_id,
        config_entry.entry_id,
    )

    _LOGGER.warning(config_entry.runtime_data)

    coordinator = config_entry.runtime_data
    sensor: SensorEntityDescription = SensorEntityDescription(
        key=KEY_CURRENT_FLOW_RATE,
        translation_key=KEY_CURRENT_FLOW_RATE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_display_precision=3,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        name=NAME_CURRENT_FLOW_RATE,
    )
    async_add_entities([DropletSensor(coordinator, sensor)])


class DropletSensor(CoordinatorEntity[DropletDataCoordinator], SensorEntity):
    """Representation of a Droplet."""

    def __init__(
        self,
        coordinator: DropletDataCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        unique_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{unique_id}_{DOMAIN}"

        entry_data = coordinator.config_entry.data
        if unique_id is not None:
            self._attr_device_info = DeviceInfo(
                manufacturer="Hydrific, part of LIXIL",
                model=entry_data[CONF_MODEL],
                name=entry_data[CONF_DEVICE_NAME],
                identifiers={(DOMAIN, unique_id)},
            )

    @property
    def available(self) -> bool:
        """Get Droplet's availability."""
        return self.coordinator.get_availability()

    @property
    def native_value(self) -> float | int | None:
        """Return the value reported by the sensor."""
        return self.coordinator.get_flow_rate()
