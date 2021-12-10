"""Support for Lutron Caseta Occupancy/Vacancy Sensors."""
from pylutron_caseta import BUTTON_STATUS_PRESSED, OCCUPANCY_GROUP_OCCUPIED

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorEntity,
)

from . import DOMAIN as CASETA_DOMAIN, LutronCasetaDevice
from .const import BRIDGE_DEVICE, BRIDGE_LEAP


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Lutron Caseta binary_sensor platform.

    Adds occupancy groups from the Caseta bridge associated with the
    config_entry as binary_sensor entities.
    """
    entities = []
    data = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data[BRIDGE_LEAP]
    bridge_device = data[BRIDGE_DEVICE]
    occupancy_groups = bridge.occupancy_groups

    for occupancy_group in occupancy_groups.values():
        entity = LutronOccupancySensor(occupancy_group, bridge, bridge_device)
        entities.append(entity)

    for button in bridge.buttons.values():
        entity = LutronPicoButton(button, bridge, bridge_device)
        entities.append(entity)

    async_add_entities(entities, True)


class LutronOccupancySensor(LutronCasetaDevice, BinarySensorEntity):
    """Representation of a Lutron occupancy group."""

    @property
    def device_class(self):
        """Flag supported features."""
        return DEVICE_CLASS_OCCUPANCY

    @property
    def is_on(self):
        """Return True iff the sensor is on."""
        return self._device["status"] == OCCUPANCY_GROUP_OCCUPIED

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_occupancy_subscriber(
            self.device_id, self.async_write_ha_state
        )

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["occupancy_group_id"]

    @property
    def unique_id(self):
        """Return a unique identifier."""
        return f"occupancygroup_{self.device_id}"

    @property
    def device_info(self):
        """Return the device info.

        Sensor entities are aggregated from one or more physical
        sensors by each room. Therefore, there shouldn't be devices
        related to any sensor entities.
        """
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id}


class LutronPicoButton(LutronCasetaDevice, BinarySensorEntity):
    """Representation of a Lutron occupancy group."""

    @property
    def is_on(self):
        """Return the brightness of the light."""
        return self._device["current_state"] == BUTTON_STATUS_PRESSED

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_button_subscriber(self.device_id, self._handle_event)

    def _handle_event(self, event_type):
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._device["name"] + str(self._device["button_number"])

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["device_id"]

    @property
    def unique_id(self):
        """Return a unique identifier."""
        return f"pico_{self.device_id}"

    @property
    def device_info(self):
        """Return the device info.

        Sensor entities are aggregated from one or more physical
        sensors by each room. Therefore, there shouldn't be devices
        related to any sensor entities.
        """
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id}
