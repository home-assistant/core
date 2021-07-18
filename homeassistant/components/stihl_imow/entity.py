"""BaseEntity for iMow Sensors."""
from imow.common.mowerstate import MowerState

from homeassistant.const import ATTR_MANUFACTURER
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ICON,
    ATTR_ID,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_PICTURE,
    ATTR_SW_VERSION,
    ATTR_TYPE,
    ATTR_UOM,
    DOMAIN,
)
from .maps import IMOW_SENSORS_MAP


class ImowBaseEntity(CoordinatorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, device, idx, mower_state_property):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.idx = idx
        self.key_device_infos = device
        self.property_name = mower_state_property
        self.cleaned_property_name = mower_state_property.replace("_", " ")

    @property
    def mowerstate(self) -> MowerState:
        """Return device object from coordinator."""
        return self.coordinator.data

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.get_value_from_mowerstate()

    def get_value_from_mowerstate(self):
        """Extract values based on property cmoplexity."""
        if "_" in self.property_name:  # Complex Entity
            return getattr(self.mowerstate, self.property_name.split("_")[0])[
                self.property_name.split("_")[1]
            ]

        else:
            return getattr(self.mowerstate, self.property_name)

    @property
    def device_info(self):
        """Provide info for device registration."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers
                # within a specific domain
                (
                    DOMAIN,
                    self.key_device_infos[ATTR_ID],
                ),
            },
            ATTR_NAME: self.key_device_infos[ATTR_NAME],
            ATTR_MANUFACTURER: self.key_device_infos[ATTR_MANUFACTURER],
            ATTR_MODEL: self.key_device_infos[ATTR_MODEL],
            ATTR_SW_VERSION: self.key_device_infos[ATTR_SW_VERSION],
        }

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self.property_name in IMOW_SENSORS_MAP:
            if IMOW_SENSORS_MAP[self.property_name][ATTR_TYPE]:
                return IMOW_SENSORS_MAP[self.property_name][ATTR_TYPE]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self.property_name in IMOW_SENSORS_MAP:
            if IMOW_SENSORS_MAP[self.property_name][ATTR_UOM]:
                return IMOW_SENSORS_MAP[self.property_name][ATTR_UOM]

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        if (
            self.property_name in IMOW_SENSORS_MAP
            and IMOW_SENSORS_MAP[self.property_name][ATTR_PICTURE]
        ):
            if self.mowerstate.mowerImageThumbnailUrl:
                return self.mowerstate.mowerImageThumbnailUrl

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.key_device_infos[ATTR_NAME]} {self.cleaned_property_name}"

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return (
            f"{self.key_device_infos[ATTR_ID]}_" f"{self.idx}_" f"{self.property_name}"
        )

    @property
    def icon(self):
        """Icon of the entity."""
        if self.property_name in IMOW_SENSORS_MAP:
            return IMOW_SENSORS_MAP[self.property_name][ATTR_ICON]
        return self._attr_icon

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()
