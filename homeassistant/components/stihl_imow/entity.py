"""BaseEntity for iMow Sensors."""
from homeassistant.const import STATE_OFF
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .maps import IMOW_SENSORS_MAP


class ImowBaseEntity(CoordinatorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, device, idx, mower_state_property):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.idx = idx
        self.sensor_data = coordinator.data[1]
        self.key_device_infos = device
        self.property_name = mower_state_property
        self.cleaned_property_name = mower_state_property.replace("_", " ")
        self._state = self.sensor_data[self.property_name]

        if (
            self.property_name in IMOW_SENSORS_MAP
            and IMOW_SENSORS_MAP[self.property_name]["picture"]
        ):
            if self.sensor_data["mowerImageThumbnailUrl"]:
                self._attr_entity_picture = self.sensor_data["mowerImageThumbnailUrl"]

    @property
    def state(self) -> StateType:
        """Return the state of the entity."""
        return self._state if self._state is not None else STATE_OFF

    @property
    def device_info(self):
        """Provide info for device registration."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers
                # within a specific domain
                (
                    DOMAIN,
                    self.key_device_infos["id"],
                ),
            },
            "name": self.key_device_infos["name"],
            "manufacturer": self.key_device_infos["manufacturer"],
            "model": self.key_device_infos["model"],
            "sw_version": self.key_device_infos["sw_version"],
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.key_device_infos['name']} {self.cleaned_property_name}"

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return f"{self.key_device_infos['id']}_{self.idx}_{self.property_name}"

    @property
    def icon(self):
        """Icon of the entity."""
        if self.property_name in IMOW_SENSORS_MAP:
            return IMOW_SENSORS_MAP[self.property_name]["icon"]
        return self._attr_icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.property_name in IMOW_SENSORS_MAP:
            return IMOW_SENSORS_MAP[self.property_name]["uom"]
        return self._attr_unit_of_measurement

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self.property_name in IMOW_SENSORS_MAP:
            return IMOW_SENSORS_MAP[self.property_name]["type"]
        return self._attr_device_class
