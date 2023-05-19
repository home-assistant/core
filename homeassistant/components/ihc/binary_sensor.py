"""Support for IHC binary sensors."""

from __future__ import annotations

from ihcsdk.ihccontroller import IHCController

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .const import CONF_INVERTING, DOMAIN, IHC_CONTROLLER
from .ihcdevice import IHCDevice


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Load IHC binary sensors based on a config entry."""
    controller_id: str = str(entry.unique_id)
    controller_data = hass.data[DOMAIN][controller_id]
    ihc_controller: IHCController = controller_data[IHC_CONTROLLER]
    sensors = []
    if "binary_sensor" in controller_data and controller_data["binary_sensor"]:
        for name, device in controller_data["binary_sensor"].items():
            ihc_id = device["ihc_id"]
            product_cfg = device["product_cfg"]
            product = device["product"]
            sensor = IHCBinarySensor(
                ihc_controller,
                controller_id,
                name,
                ihc_id,
                product_cfg.get(CONF_TYPE),
                product_cfg[CONF_INVERTING],
                product,
            )
            sensors.append(sensor)
        async_add_entities(sensors)


class IHCBinarySensor(IHCDevice, BinarySensorEntity):
    """IHC Binary Sensor.

    The associated IHC resource can be any in or output from a IHC product
    or function block, but it must be a boolean ON/OFF resources.
    """

    def __init__(
        self,
        ihc_controller: IHCController,
        controller_id: str,
        name: str,
        ihc_id: int,
        sensor_type: str,
        inverting: bool,
        product=None,
    ) -> None:
        """Initialize the IHC binary sensor."""
        super().__init__(ihc_controller, controller_id, name, ihc_id, product)
        self._attr_device_class = try_parse_enum(BinarySensorDeviceClass, sensor_type)
        self.inverting = inverting

    def on_ihc_change(self, ihc_id, value):
        """IHC resource has changed."""
        if self.inverting:
            self._attr_is_on = not value
        else:
            self._attr_is_on = value
        self.schedule_update_ha_state()
