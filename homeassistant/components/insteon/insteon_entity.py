"""Insteon base entity."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import (
    SIGNAL_LOAD_ALDB,
    SIGNAL_PRINT_ALDB,
    SIGNAL_SAVE_DEVICES,
    STATE_NAME_LABEL_MAP,
)
from .utils import print_aldb_to_log

_LOGGER = logging.getLogger(__name__)


class InsteonEntity(Entity):
    """INSTEON abstract base entity."""

    def __init__(self, device, group):
        """Initialize the INSTEON binary sensor."""
        self._insteon_device_group = device.groups[group]
        self._insteon_device = device

    def __hash__(self):
        """Return the hash of the Insteon Entity."""
        return hash(self._insteon_device)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the address of the node."""
        return str(self._insteon_device.address)

    @property
    def group(self):
        """Return the INSTEON group that the entity responds to."""
        return self._insteon_device_group.group

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self._insteon_device_group.group == 0x01:
            uid = self._insteon_device.id
        else:
            uid = f"{self._insteon_device.id}_{self._insteon_device_group.group}"
        return uid

    @property
    def name(self):
        """Return the name of the node (used for Entity_ID)."""
        # Set a base description
        description = self._insteon_device.description
        if description is None:
            description = "Unknown Device"
        # Get an extension label if there is one
        extension = self._get_label()
        if extension:
            extension = f" {extension}"
        return f"{description} {self._insteon_device.address}{extension}"

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        return {"insteon_address": self.address, "insteon_group": self.group}

    @callback
    def async_entity_update(self, name, address, value, group):
        """Receive notification from transport that new data exists."""
        _LOGGER.debug(
            "Received update for device %s group %d value %s", address, group, value,
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register INSTEON update events."""
        _LOGGER.debug(
            "Tracking updates for device %s group %d name %s",
            self.address,
            self.group,
            self._insteon_device_group.name,
        )
        self._insteon_device_group.subscribe(self.async_entity_update)
        load_signal = f"{self.entity_id}_{SIGNAL_LOAD_ALDB}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, load_signal, self._async_read_aldb)
        )
        print_signal = f"{self.entity_id}_{SIGNAL_PRINT_ALDB}"
        async_dispatcher_connect(self.hass, print_signal, self._print_aldb)

    async def _async_read_aldb(self, reload):
        """Call device load process and print to log."""
        await self._insteon_device.aldb.async_load(refresh=reload)
        self._print_aldb()
        async_dispatcher_send(self.hass, SIGNAL_SAVE_DEVICES)

    def _print_aldb(self):
        """Print the device ALDB to the log file."""
        print_aldb_to_log(self._insteon_device.aldb)

    def _get_label(self):
        """Get the device label for grouped devices."""
        label = ""
        if len(self._insteon_device.groups) > 1:
            if self._insteon_device_group.name in STATE_NAME_LABEL_MAP:
                label = STATE_NAME_LABEL_MAP[self._insteon_device_group.name]
            else:
                label = f"Group {self.group:d}"
        return label
