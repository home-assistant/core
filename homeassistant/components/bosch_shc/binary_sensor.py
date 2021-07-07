"""Platform for binarysensor integration."""
from boschshcpy import SHCBatteryDevice, SHCSession, SHCShutterContact

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
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

    for binary_sensor in (
        session.device_helper.motion_detectors
        + session.device_helper.shutter_contacts
        + session.device_helper.smoke_detectors
        + session.device_helper.thermostats
        + session.device_helper.twinguards
        + session.device_helper.universal_switches
        + session.device_helper.wallthermostats
        + session.device_helper.water_leakage_detectors
    ):
        if binary_sensor.supports_batterylevel:
            entities.append(
                BatterySensor(
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


class BatterySensor(SHCEntity, BinarySensorEntity):
    """Representation of a SHC battery reporting sensor."""

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device.serial}_battery"

    @property
    def name(self):
        """Return the name of this sensor."""
        return f"{self._device.name} Battery"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return (
            self._device.batterylevel != SHCBatteryDevice.BatteryLevelService.State.OK
        )

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return DEVICE_CLASS_BATTERY
