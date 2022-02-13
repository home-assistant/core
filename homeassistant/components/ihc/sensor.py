"""Support for IHC sensors."""
from __future__ import annotations

from ihcsdk.ihccontroller import IHCController

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_system import TEMPERATURE_UNITS

from .const import DOMAIN, IHC_CONTROLLER
from .ihcdevice import IHCDevice


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Load IHC sensors based on a config entry."""
    controller_id: str = str(entry.unique_id)
    controller_data = hass.data[DOMAIN][controller_id]
    ihc_controller: IHCController = controller_data[IHC_CONTROLLER]
    sensors = []
    if "sensor" in controller_data and controller_data["sensor"]:
        for name, device in controller_data["sensor"].items():
            ihc_id = device["ihc_id"]
            product_cfg = device["product_cfg"]
            product = device["product"]
            unit = product_cfg[CONF_UNIT_OF_MEASUREMENT]
            sensor = IHCSensor(
                ihc_controller,
                controller_id,
                name,
                ihc_id,
                unit,
                product,
            )
            sensors.append(sensor)
        async_add_entities(sensors)


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
