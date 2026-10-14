"""Platform for binarysensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from boschshcpy import (
    BatteryLevelService,
    SHCBatteryDevice,
    SHCShutterContact,
    ShutterContactService,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SHCShutterContactSensorEntityDescription(BinarySensorEntityDescription):
    """Describes a SHC shutter contact binary sensor."""

    is_on_fn: Callable[[SHCShutterContact], bool]


SHUTTER_CONTACT_DESCRIPTION = SHCShutterContactSensorEntityDescription(
    key="shutter_contact",
    is_on_fn=lambda device: device.state is ShutterContactService.State.OPEN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC binary sensor platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    entities: list[BinarySensorEntity] = [
        ShutterContactSensor(
            hass=hass,
            device=binary_sensor,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            entity_description=SHUTTER_CONTACT_DESCRIPTION,
        )
        for binary_sensor in (
            *session.device_helper.shutter_contacts,
            *session.device_helper.shutter_contacts2,
        )
    ]

    entities.extend(
        BatterySensor(
            hass=hass,
            device=binary_sensor,
            parent_id=shc_info.unique_id,
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


class ShutterContactSensor(SHCEntity, BinarySensorEntity):
    """Representation of an SHC shutter contact sensor."""

    _attr_name = None
    _device: SHCShutterContact
    entity_description: SHCShutterContactSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
        entity_description: SHCShutterContactSensorEntityDescription,
    ) -> None:
        """Initialize an SHC shutter contact sensor."""
        self.entity_description = entity_description
        super().__init__(hass, device, parent_id, entry_id)
        switcher: dict[str | None, BinarySensorDeviceClass] = {
            "ENTRANCE_DOOR": BinarySensorDeviceClass.DOOR,
            "REGULAR_WINDOW": BinarySensorDeviceClass.WINDOW,
            "FRENCH_WINDOW": BinarySensorDeviceClass.DOOR,
            "GENERIC": BinarySensorDeviceClass.WINDOW,
        }
        self._attr_device_class = switcher.get(
            self._device.device_class, BinarySensorDeviceClass.WINDOW
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.entity_description.is_on_fn(self._device)


class BatterySensor(SHCEntity, BinarySensorEntity):
    """Representation of an SHC battery reporting sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _device: SHCBatteryDevice

    def __init__(
        self, hass: HomeAssistant, device: SHCDevice, parent_id: str, entry_id: str
    ) -> None:
        """Initialize an SHC battery reporting sensor."""
        super().__init__(hass, device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_battery"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.batterylevel is not BatteryLevelService.State.OK
