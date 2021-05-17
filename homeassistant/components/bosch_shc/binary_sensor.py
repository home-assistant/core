"""Platform for binarysensor integration."""
from boschshcpy import SHCSession, SHCShutterContact

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
)

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the SHC binary sensor platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for binary_sensor in session.device_helper.shutter_contacts:
        entities.append(
            ShutterContactSensor(
                device=binary_sensor,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)


class ShutterContactSensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC shutter contact sensor."""

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._device.state == SHCShutterContact.ShutterContactService.State.OPEN

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        switcher = {
            "ENTRANCE_DOOR": DEVICE_CLASS_DOOR,
            "REGULAR_WINDOW": DEVICE_CLASS_WINDOW,
            "FRENCH_WINDOW": DEVICE_CLASS_DOOR,
            "GENERIC": DEVICE_CLASS_WINDOW,
        }
        return switcher.get(self._device.device_class, DEVICE_CLASS_WINDOW)
