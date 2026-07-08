"""Platform for binarysensor integration."""

from typing import override

from boschshcpy import (
    BatteryLevelService,
    SHCBatteryDevice,
    SHCShutterContact,
    ShutterContactService,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC binary sensor platform."""
    session = config_entry.runtime_data.session
    parent_id = config_entry.runtime_data.parent_id

    entities: list[BinarySensorEntity] = [
        ShutterContactSensor(
            device=binary_sensor,
            parent_id=parent_id,
            entry_id=config_entry.entry_id,
        )
        for binary_sensor in (
            *session.device_helper.shutter_contacts,
            *session.device_helper.shutter_contacts2,
        )
    ]

    entities.extend(
        BatterySensor(
            device=binary_sensor,
            parent_id=parent_id,
            entry_id=config_entry.entry_id,
        )
        for binary_sensor in (
            *session.device_helper.motion_detectors,
            *session.device_helper.shutter_contacts,
            *session.device_helper.shutter_contacts2,
            *session.device_helper.smoke_detectors,
            *session.device_helper.thermostats,
            *session.device_helper.twinguards,
            *session.device_helper.universal_switches,
            *session.device_helper.wallthermostats,
            *session.device_helper.water_leakage_detectors,
        )
    )

    async_add_entities(entities)


class ShutterContactSensor(SHCEntity[SHCShutterContact], BinarySensorEntity):
    """Representation of an SHC shutter contact sensor."""

    _attr_name = None

    def __init__(
        self, device: SHCShutterContact, parent_id: str, entry_id: str
    ) -> None:
        """Initialize an SHC shutter contact sensor."""
        super().__init__(device, parent_id, entry_id)
        switcher = {
            "ENTRANCE_DOOR": BinarySensorDeviceClass.DOOR,
            "REGULAR_WINDOW": BinarySensorDeviceClass.WINDOW,
            "FRENCH_WINDOW": BinarySensorDeviceClass.DOOR,
            "GENERIC": BinarySensorDeviceClass.WINDOW,
        }
        device_class = self._device.device_class
        self._attr_device_class = (
            switcher.get(device_class, BinarySensorDeviceClass.WINDOW)
            if device_class is not None
            else BinarySensorDeviceClass.WINDOW
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.state is ShutterContactService.State.OPEN


class BatterySensor(SHCEntity[SHCBatteryDevice], BinarySensorEntity):
    """Representation of an SHC battery reporting sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, device: SHCBatteryDevice, parent_id: str, entry_id: str) -> None:
        """Initialize an SHC battery reporting sensor."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_battery"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.batterylevel is not BatteryLevelService.State.OK
