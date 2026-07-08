"""Platform for binarysensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from boschshcpy import (
    BatteryLevelService,
    SHCBatteryDevice,
    SHCDevice,
    SHCShutterContact,
    ShutterContactService,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity


@dataclass(frozen=True, kw_only=True)
class SHCBinarySensorEntityDescription[_DeviceT: SHCDevice](
    BinarySensorEntityDescription
):
    """Class describing SHC binary sensor entities."""

    is_on_fn: Callable[[_DeviceT], bool]


SHUTTER_CONTACT_DESCRIPTION = SHCBinarySensorEntityDescription[SHCShutterContact](
    key="shutter_contact",
    is_on_fn=lambda device: device.state is ShutterContactService.State.OPEN,
)

BATTERY_DESCRIPTION = SHCBinarySensorEntityDescription[SHCBatteryDevice](
    key="battery",
    device_class=BinarySensorDeviceClass.BATTERY,
    is_on_fn=lambda device: device.batterylevel is not BatteryLevelService.State.OK,
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

    async_add_entities(
        ShutterContactSensor(
            device=binary_sensor,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            entity_description=SHUTTER_CONTACT_DESCRIPTION,
        )
        for binary_sensor in (
            *session.device_helper.shutter_contacts,
            *session.device_helper.shutter_contacts2,
        )
    )

    async_add_entities(
        BatterySensor(
            device=binary_sensor,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            entity_description=BATTERY_DESCRIPTION,
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


class ShutterContactSensor(SHCEntity[SHCShutterContact], BinarySensorEntity):
    """Representation of an SHC shutter contact sensor."""

    _attr_name = None
    entity_description: SHCBinarySensorEntityDescription[SHCShutterContact]

    def __init__(
        self,
        device: SHCShutterContact,
        parent_id: str,
        entry_id: str,
        entity_description: SHCBinarySensorEntityDescription[SHCShutterContact],
    ) -> None:
        """Initialize an SHC shutter contact sensor."""
        super().__init__(device, parent_id, entry_id)
        self.entity_description = entity_description
        switcher = {
            "ENTRANCE_DOOR": BinarySensorDeviceClass.DOOR,
            "REGULAR_WINDOW": BinarySensorDeviceClass.WINDOW,
            "FRENCH_WINDOW": BinarySensorDeviceClass.DOOR,
            "GENERIC": BinarySensorDeviceClass.WINDOW,
        }
        self._attr_device_class = switcher.get(
            self._device.device_class or "", BinarySensorDeviceClass.WINDOW
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.entity_description.is_on_fn(self._device)


class BatterySensor(SHCEntity[SHCBatteryDevice], BinarySensorEntity):
    """Representation of an SHC battery reporting sensor."""

    entity_description: SHCBinarySensorEntityDescription[SHCBatteryDevice]

    def __init__(
        self,
        device: SHCBatteryDevice,
        parent_id: str,
        entry_id: str,
        entity_description: SHCBinarySensorEntityDescription[SHCBatteryDevice],
    ) -> None:
        """Initialize an SHC battery reporting sensor."""
        super().__init__(device, parent_id, entry_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.serial}_battery"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.entity_description.is_on_fn(self._device)
