"""Support for IHC sensors."""
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.helpers.entity import Entity

from . import IHC_CONTROLLER, IHC_DATA, IHC_INFO
from .ihcdevice import IHCDevice

DEPENDENCIES = ['ihc']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the IHC sensor platform."""
    if discovery_info is None:
        return
    devices = []
    for name, device in discovery_info.items():
        ihc_id = device['ihc_id']
        product_cfg = device['product_cfg']
        product = device['product']
        # Find controller that corresponds with device id
        ctrl_id = device['ctrl_id']
        ihc_key = IHC_DATA.format(ctrl_id)
        info = hass.data[ihc_key][IHC_INFO]
        ihc_controller = hass.data[ihc_key][IHC_CONTROLLER]
        unit = product_cfg[CONF_UNIT_OF_MEASUREMENT]
        sensor = IHCSensor(ihc_controller, name, ihc_id, info, unit, product)
        devices.append(sensor)
    add_entities(devices)


class IHCSensor(IHCDevice, Entity):
    """Implementation of the IHC sensor."""

    def __init__(self, ihc_controller, name, ihc_id: int, info: bool,
                 unit, product=None) -> None:
        """Initialize the IHC sensor."""
        super().__init__(ihc_controller, name, ihc_id, info, product)
        self._state = None
        self._unit_of_measurement = unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def on_ihc_change(self, ihc_id, value):
        """Handle IHC resource change."""
        self._state = value
        self.schedule_update_ha_state()
