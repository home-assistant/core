"""Device tracker for BMW Connected Drive vehicles."""
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from . import DOMAIN as BMW_DOMAIN, BMWConnectedDriveBaseEntity
from .const import CONF_ACCOUNT, DATA_ENTRIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the BMW ConnectedDrive tracker from config entry."""
    account = hass.data[BMW_DOMAIN][DATA_ENTRIES][config_entry.entry_id][CONF_ACCOUNT]
    entities = []

    for vehicle in account.account.vehicles:
        entities.append(BMWDeviceTracker(account, vehicle))
        if not vehicle.state.is_vehicle_tracking_enabled:
            _LOGGER.info(
                "Tracking is (currently) disabled for vehicle %s (%s), defaulting to unknown",
                vehicle.name,
                vehicle.vin,
            )
    async_add_entities(entities, True)


class BMWDeviceTracker(BMWConnectedDriveBaseEntity, TrackerEntity):
    """BMW Connected Drive device tracker."""

    _attr_force_update = False
    _attr_icon = "mdi:car"

    def __init__(self, account, vehicle):
        """Initialize the Tracker."""
        super().__init__(account, vehicle)

        self._attr_unique_id = vehicle.vin
        self._location = (
            vehicle.state.gps_position if vehicle.state.gps_position else (None, None)
        )
        self._attr_name = vehicle.name

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._location[0] if self._location else None

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._location[1] if self._location else None

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    def update(self):
        """Update state of the decvice tracker."""
        self._attr_extra_state_attributes = self._attrs
        self._location = (
            self._vehicle.state.gps_position
            if self._vehicle.state.is_vehicle_tracking_enabled
            else (None, None)
        )
