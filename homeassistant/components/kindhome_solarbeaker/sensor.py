"""Platform for sensor integration."""
# This file shows the setup for the sensors associated with the cover.
# They are setup in the same way with the call to the async_setup_entry function
# via HA from the module __init__. Each sensor has a device_class, this tells HA how
# to display it in the UI (for know types). The unit_of_measurement property tells HA
# what the unit is, so it can display the correct range. For predefined types (such as
# battery), the unit_of_measurement should match what's expected.

import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_DEVICE, DOMAIN
from .kindhome_solarbeaker_ble import KindhomeSolarbeakerDevice
from .utils import log

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the brunt platform."""
    device: KindhomeSolarbeakerDevice = hass.data[DOMAIN][entry.entry_id][DATA_DEVICE]
    log(_LOGGER, "async_setup_entry", device)

    async_add_entities([BatterySensor(device)])


# Base class in case other sensors need to be created.
class SensorBase(Entity):
    """Base representation of a Kindhome Solarbeaker Sensor."""

    should_poll = False

    def __init__(self, device):
        """Initialize the sensor."""
        self.device: KindhomeSolarbeakerDevice = device

    # To link this entity to the cover device, this property must return an
    # identifiers value matching that used in the cover, but no other information such
    # as name. If name is returned, this entity will then also become a device in the
    # HA UI.
    @property
    def device_info(self) -> DeviceInfo:
        """Device info for this entity."""
        return {
            "identifiers": {(DOMAIN, self.device.device_id)},
        }

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self.device.remove_callback(self.async_write_ha_state)


class BatterySensor(SensorBase):
    """Representation of a Sensor."""

    device_class = SensorDeviceClass.BATTERY
    _attr_unit_of_measurement = PERCENTAGE

    def __init__(self, device):
        """Initialize the sensor."""
        super().__init__(device)

        self._attr_unique_id = f"{self.device.device_id}_battery"
        self._attr_name = f"{self.device.device_name} Battery"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device.battery_level
