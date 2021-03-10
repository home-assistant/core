"""Support for KNX/IP sensors."""
import logging

from xknx.devices import Sensor as XknxSensor

from homeassistant.components.sensor import DEVICE_CLASSES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .knx_entity import KnxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up sensor(s) for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxSensor):
            entities.append(KNXSensor(hass, device))
    async_add_entities(entities)


class KNXSensor(KnxEntity, Entity):
    """Representation of a KNX sensor."""

    def __init__(self, hass: HomeAssistant, device: XknxSensor):
        """Initialize of a KNX sensor."""
        if device.ha_value_template is not None:
            device.ha_value_template.hass = hass
        super().__init__(device)

    @property
    def state(self):
        """Return the state of the sensor."""
        state = self._device.resolve_state()
        template = self._device.ha_value_template
        if template is not None and state is not None:
            try:
                return template.async_render({"value": state})
            except TemplateError as ex:
                _LOGGER.error(
                    "Error while rendering template for '%s'. %s", self.name, ex
                )
                return None
        return state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._device.unit_of_measurement()

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        device_class = self._device.ha_device_class()
        if device_class in DEVICE_CLASSES:
            return device_class
        return None

    @property
    def force_update(self) -> bool:
        """
        Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return self._device.always_callback
