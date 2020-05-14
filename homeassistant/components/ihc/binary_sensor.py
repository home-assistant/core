"""Support for IHC binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_TYPE

from . import IHC_CONTROLLER, IHC_INFO
from .const import CONF_INVERTING
from .ihcdevice import IHCDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the IHC binary sensor platform."""
    if discovery_info is None:
        return
    devices = []
    for name, device in discovery_info.items():
        ihc_id = device["ihc_id"]
        product_cfg = device["product_cfg"]
        product = device["product"]
        # Find controller that corresponds with device id
        ctrl_id = device["ctrl_id"]
        ihc_key = f"ihc{ctrl_id}"
        info = hass.data[ihc_key][IHC_INFO]
        ihc_controller = hass.data[ihc_key][IHC_CONTROLLER]

        sensor = IHCBinarySensor(
            ihc_controller,
            name,
            ihc_id,
            info,
            product_cfg.get(CONF_TYPE),
            product_cfg[CONF_INVERTING],
            product,
        )
        devices.append(sensor)
    add_entities(devices)


class IHCBinarySensor(IHCDevice, BinarySensorDevice):
    """IHC Binary Sensor.

    The associated IHC resource can be any in or output from a IHC product
    or function block, but it must be a boolean ON/OFF resources.
    """

    def __init__(
        self,
        ihc_controller,
        name,
        ihc_id: int,
        info: bool,
        sensor_type: str,
        inverting: bool,
        product=None,
    ) -> None:
        """Initialize the IHC binary sensor."""
        super().__init__(ihc_controller, name, ihc_id, info, product)
        self._state = None
        self._sensor_type = sensor_type
        self.inverting = inverting

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._state

    def on_ihc_change(self, ihc_id, value):
        """IHC resource has changed."""
        if self.inverting:
            self._state = not value
        else:
            self._state = value
        self.schedule_update_ha_state()
