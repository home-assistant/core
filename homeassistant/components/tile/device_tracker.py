"""Support for Tile device trackers."""
import logging

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_GPS
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DATA_COORDINATOR, DATA_TILE, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_ALTITUDE = "altitude"
ATTR_CONNECTION_STATE = "connection_state"
ATTR_IS_DEAD = "is_dead"
ATTR_IS_LOST = "is_lost"
ATTR_LAST_LOST_TIMESTAMP = "last_lost_timestamp"
ATTR_RING_STATE = "ring_state"
ATTR_TILE_NAME = "tile_name"
ATTR_VOIP_STATE = "voip_state"

DEFAULT_ATTRIBUTION = "Data provided by Tile"
DEFAULT_ICON = "mdi:view-grid"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Tile device trackers."""
    async_add_entities(
        [
            TileDeviceTracker(
                hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][tile_uuid], tile
            )
            for tile_uuid, tile in hass.data[DOMAIN][DATA_TILE][entry.entry_id].items()
        ]
    )


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Detect a legacy configuration and import it."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )
    )

    _LOGGER.info(
        "Your Tile configuration has been imported into the UI; "
        "please remove it from configuration.yaml"
    )

    return True


class TileDeviceTracker(CoordinatorEntity, TrackerEntity):
    """Representation of a network infrastructure device."""

    def __init__(self, coordinator, tile):
        """Initialize."""
        super().__init__(coordinator)
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._tile = tile

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success and not self._tile.dead

    @property
    def battery_level(self):
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return DEFAULT_ICON

    @property
    def location_accuracy(self):
        """Return the location accuracy of the device.

        Value in meters.
        """
        return self._tile.accuracy

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return self._tile.latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return self._tile.longitude

    @property
    def name(self):
        """Return the name."""
        return self._tile.name

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"tile_{self._tile.uuid}"

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @callback
    def _handle_coordinator_update(self):
        """Respond to a DataUpdateCoordinator update."""
        self._update_from_latest_data()
        self.async_write_ha_state()

    @callback
    def _update_from_latest_data(self):
        """Update the entity from the latest data."""
        self._attrs.update(
            {
                ATTR_ALTITUDE: self._tile.altitude,
                ATTR_IS_LOST: self._tile.lost,
                ATTR_LAST_LOST_TIMESTAMP: self._tile.lost_timestamp,
                ATTR_RING_STATE: self._tile.ring_state,
                ATTR_VOIP_STATE: self._tile.voip_state,
            }
        )

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._update_from_latest_data()
