"""Support for IHC binary sensors."""

from __future__ import annotations

from ihcsdk.ihccontroller import IHCController

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.enum import try_parse_enum

from .const import CONF_INVERTING, DOMAIN, IHC_CONTROLLER
from .entity import IHCEntity


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the IHC binary sensor platform."""
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
        sensor = IHCBinarySensor(
            ihc_controller,
            controller_id,
            name,
            ihc_id,
            product_cfg.get(CONF_TYPE),
            product_cfg[CONF_INVERTING],
            product,
        )
        devices.append(sensor)
    add_entities(devices)


class IHCBinarySensor(IHCEntity, BinarySensorEntity):
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
