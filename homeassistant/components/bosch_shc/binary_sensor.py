"""Platform for binarysensor integration."""
from __future__ import annotations

from boschshcpy import SHCBatteryDevice, SHCSession, SHCShutterContact
from boschshcpy.device import SHCDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SHC binary sensor platform."""
    entities: list[BinarySensorEntity] = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for binary_sensor in (
        session.device_helper.shutter_contacts + session.device_helper.shutter_contacts2
    ):
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
        + session.device_helper.shutter_contacts2
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

    async_add_entities(entities)


class ShutterContactSensor(SHCEntity, BinarySensorEntity):
    """Representation of an SHC shutter contact sensor."""

    _attr_name = None

    def __init__(self, device: SHCDevice, parent_id: str, entry_id: str) -> None:
        """Initialize an SHC shutter contact sensor.."""
        super().__init__(device, parent_id, entry_id)
        switcher = {
            "ENTRANCE_DOOR": BinarySensorDeviceClass.DOOR,
            "REGULAR_WINDOW": BinarySensorDeviceClass.WINDOW,
            "FRENCH_WINDOW": BinarySensorDeviceClass.DOOR,
            "GENERIC": BinarySensorDeviceClass.WINDOW,
        }
        self._attr_device_class = switcher.get(
            self._device.device_class, BinarySensorDeviceClass.WINDOW
        )

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._device.state == SHCShutterContact.ShutterContactService.State.OPEN


class BatterySensor(SHCEntity, BinarySensorEntity):
    """Representation of an SHC battery reporting sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, device: SHCDevice, parent_id: str, entry_id: str) -> None:
        """Initialize an SHC battery reporting sensor."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_battery"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return (
            self._device.batterylevel != SHCBatteryDevice.BatteryLevelService.State.OK
        )
