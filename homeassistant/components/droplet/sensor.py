"""Platform for sensor integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DropletConfigEntry
from .const import BRAND, DOMAIN
from .droplet import Droplet


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DropletConfigEntry,
    async_add_entities: AddEntitiesCallback,  # pylint: disable=hass-argument-type
) -> None:
    """Add sensors for passed config_entry in HA."""
    #    hub = config_entry.runtime_data
    # Not how you're supposed to do this
    async_add_entities([DropletSensor("localhost", 3333)])


class DropletSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_name = "Flow Rate"
    _attr_unique_id = "ASKFD497134_droplet"
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-circle"

    def __init__(self, hostname, port):
        """Initialize Droplet sensor."""
        self.droplet = Droplet(3333, "localhost", self.set_flow)

        self.mac = "abc"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self.mac}")},
            # serial_number=coordinator.data.info.serial_number,
            manufacturer=BRAND,
            # model=coordinator.data.info.product_name,
            name=f"{BRAND} {DOMAIN}",
            # sw_version=f"{coordinator.data.info.firmware_version} ({coordinator.data.info.firmware_build_number})",
            # hw_version=str(coordinator.data.info.hardware_board_type),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    def set_flow(self, flow):
        """Set flow and schedule update of HA state."""
        self._attr_native_value = flow
        self.schedule_update_ha_state()
