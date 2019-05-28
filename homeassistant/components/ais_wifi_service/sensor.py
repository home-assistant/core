"""Support for Drive sensors."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from .config_flow import configured_drivers
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an Drive sensor based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a drive sensor based on a rclone config entry."""
    from homeassistant.components.ais_drives_service import rclone_get_remotes_long, DRIVES_TYPES
    remotes = rclone_get_remotes_long()
    conf_drives = configured_drivers(hass)
    sensors = []
    for remote in remotes:
        drive_type = remote["type"]
        code, icon = DRIVES_TYPES[drive_type]
        srn = slugify(remote["name"])
        # if srn in conf_drives:
        #     _LOGGER.info('Drive exists ' + srn)
        # else:
        #     # check if sensor exists
        #     #state = hass.states.get('sensor.ais_drives_service_' + srn)
        #     #if state is None:
        sensors.append(DriveSensor(srn, icon))

    async_add_entities(sensors, True)


class DriveSensor(Entity):
    """Implementation of a Drive sensor."""

    def __init__(self, name, icon):
        """Initialize the Drive sensor."""
        self._icon = icon
        self._name = name
        self._data = None
        self._attrs = {}

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return 1

    # @property
    # def unit_of_measurement(self):
    #     """Return the unit of measurement of this entity, if any."""
    #     return '%'

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        pass

    async def async_update(self):
        """Get the latest data and update the state."""
        try:
            self._data = 1
        except KeyError:
            return
