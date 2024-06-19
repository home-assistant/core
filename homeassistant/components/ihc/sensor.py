"""Support for IHC sensors."""

from __future__ import annotations

from ihcsdk.ihccontroller import IHCController

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_system import TEMPERATURE_UNITS

from .const import DOMAIN, IHC_CONTROLLER
from .ihcdevice import IHCDevice


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the IHC sensor platform."""
    if discovery_info is None:
        return
    devices = []
    for name, device in discovery_info.items():
        ihc_id = device["ihc_id"]
        product_cfg = device["product_cfg"]
        product = device["product"]
        # Find controller that corresponds with device id
        controller_id = device["ctrl_id"]
        ihc_controller: IHCController = hass.data[DOMAIN][controller_id][IHC_CONTROLLER]
        unit = product_cfg[CONF_UNIT_OF_MEASUREMENT]
        sensor = IHCSensor(ihc_controller, controller_id, name, ihc_id, unit, product)
        devices.append(sensor)
    add_entities(devices)


class IHCSensor(IHCDevice, SensorEntity):
    """Implementation of the IHC sensor."""

    def __init__(
        self,
        ihc_controller: IHCController,
        controller_id: str,
        name: str,
        ihc_id: int,
        unit: str,
        product=None,
    ) -> None:
        """Initialize the IHC sensor."""
        super().__init__(ihc_controller, controller_id, name, ihc_id, product)
        self._attr_native_unit_of_measurement = unit
        if unit in TEMPERATURE_UNITS:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE

    def on_ihc_change(self, ihc_id, value):
        """Handle IHC resource change."""
        self._attr_native_value = value
        self.schedule_update_ha_state()
