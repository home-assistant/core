"""Support for MyQ gateways."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorDevice,
)

from .const import (
    DOMAIN,
    KNOWN_MODELS,
    MANUFACTURER,
    MYQ_COORDINATOR,
    MYQ_DEVICE_FAMILY,
    MYQ_DEVICE_FAMILY_GATEWAY,
    MYQ_DEVICE_STATE,
    MYQ_DEVICE_STATE_ONLINE,
    MYQ_GATEWAY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mysq covers."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    myq = data[MYQ_GATEWAY]
    coordinator = data[MYQ_COORDINATOR]

    entities = []

    for device in myq.devices.values():
        if device.device_json[MYQ_DEVICE_FAMILY] == MYQ_DEVICE_FAMILY_GATEWAY:
            entities.append(MyQBinarySensorDevice(coordinator, device))

    async_add_entities(entities, True)


class MyQBinarySensorDevice(BinarySensorDevice):
    """Representation of a MyQ gateway."""

    def __init__(self, coordinator, device):
        """Initialize with API object, device id."""
        self._coordinator = coordinator
        self._device = device

    @property
    def device_class(self):
        """We track connectivity for gateways."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return f"{self._device.name} MyQ Gateway"

    @property
    def is_on(self):
        """Return if the device is online."""
        if not self._coordinator.last_update_success:
            return False

        # Not all devices report online so assume True if its missing
        return self._device.device_json[MYQ_DEVICE_STATE].get(
            MYQ_DEVICE_STATE_ONLINE, True
        )

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device.device_id

    async def async_update(self):
        """Update status of cover."""
        await self._coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Return the device_info of the device."""
        device_info = {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "sw_version": self._device.firmware_version,
        }
        model = KNOWN_MODELS.get(self._device.device_id[2:4])
        if model:
            device_info["model"] = model

        return device_info

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
