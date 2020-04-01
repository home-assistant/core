"""Insteon base entity."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    DOMAIN,
    INSTEON_ENTITIES,
    SIGNAL_LOAD_ALDB,
    SIGNAL_PRINT_ALDB,
    STATE_NAME_LABEL_MAP,
)
from .utils import print_aldb_to_log

_LOGGER = logging.getLogger(__name__)


class InsteonEntity(Entity):
    """INSTEON abstract base entity."""

    def __init__(self, device, state_key):
        """Initialize the INSTEON binary sensor."""
        self._insteon_device_state = device.states[state_key]
        self._insteon_device = device
        self._insteon_device.aldb.add_loaded_callback(self._aldb_loaded)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the address of the node."""
        return self._insteon_device.address.human

    @property
    def group(self):
        """Return the INSTEON group that the entity responds to."""
        return self._insteon_device_state.group

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self._insteon_device_state.group == 0x01:
            uid = self._insteon_device.id
        else:
            uid = f"{self._insteon_device.id}_{self._insteon_device_state.group}"
        return uid

    @property
    def name(self):
        """Return the name of the node (used for Entity_ID)."""
        # Set a base description
        description = self._insteon_device.description
        if self._insteon_device.description is None:
            description = "Unknown Device"

        # Get an extension label if there is one
        extension = self._get_label()
        if extension:
            extension = f" {extension}"
        name = f"{description} {self._insteon_device.address.human}{extension}"
        return name

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        attributes = {"insteon_address": self.address, "insteon_group": self.group}
        return attributes

    @callback
    def async_entity_update(self, deviceid, group, val):
        """Receive notification from transport that new data exists."""
        _LOGGER.debug(
            "Received update for device %s group %d value %s",
            deviceid.human,
            group,
            val,
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register INSTEON update events."""
        _LOGGER.debug(
            "Tracking updates for device %s group %d statename %s",
            self.address,
            self.group,
            self._insteon_device_state.name,
        )
        self._insteon_device_state.register_updates(self.async_entity_update)
        self.hass.data[DOMAIN][INSTEON_ENTITIES].add(self.entity_id)
        load_signal = f"{self.entity_id}_{SIGNAL_LOAD_ALDB}"
        async_dispatcher_connect(self.hass, load_signal, self._load_aldb)
        print_signal = f"{self.entity_id}_{SIGNAL_PRINT_ALDB}"
        async_dispatcher_connect(self.hass, print_signal, self._print_aldb)

    def _load_aldb(self, reload=False):
        """Load the device All-Link Database."""
        if reload:
            self._insteon_device.aldb.clear()
        self._insteon_device.read_aldb()

    def _print_aldb(self):
        """Print the device ALDB to the log file."""
        print_aldb_to_log(self._insteon_device.aldb)

    @callback
    def _aldb_loaded(self):
        """All-Link Database loaded for the device."""
        self._print_aldb()

    def _get_label(self):
        """Get the device label for grouped devices."""
        label = ""
        if len(self._insteon_device.states) > 1:
            if self._insteon_device_state.name in STATE_NAME_LABEL_MAP:
                label = STATE_NAME_LABEL_MAP[self._insteon_device_state.name]
            else:
                label = f"Group {self.group:d}"
        return label
