"""Support for MyQ gateways."""
from pymyq.const import (
    DEVICE_STATE as MYQ_DEVICE_STATE,
    DEVICE_STATE_ONLINE as MYQ_DEVICE_STATE_ONLINE,
    KNOWN_MODELS,
    MANUFACTURER,
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MYQ_COORDINATOR, MYQ_GATEWAY


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mysq covers."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    myq = data[MYQ_GATEWAY]
    coordinator = data[MYQ_COORDINATOR]

    entities = []

    for device in myq.gateways.values():
        entities.append(MyQBinarySensorEntity(coordinator, device))

    async_add_entities(entities)


class MyQBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Representation of a MyQ gateway."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(self, coordinator, device):
        """Initialize with API object, device id."""
        super().__init__(coordinator)
        self._device = device

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return f"{self._device.name} MyQ Gateway"

    @property
    def is_on(self):
        """Return if the device is online."""
        if not self.coordinator.last_update_success:
            return False

        # Not all devices report online so assume True if its missing
        return self._device.device_json[MYQ_DEVICE_STATE].get(
            MYQ_DEVICE_STATE_ONLINE, True
        )

    @property
    def available(self) -> bool:
        """Entity is always available."""
        return True

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device.device_id

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
