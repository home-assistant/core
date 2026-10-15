"""Support for iCloud sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import StateType

from .account import IcloudAccount, IcloudConfigEntry, IcloudDevice
from .const import DEVICE_STATUS_CODES
from .entity import IcloudDeviceEntity

BATTERY_STATUS_OPTIONS = ["charging", "full", "not_charging"]

_LOCATION_TYPE_OPTIONS = ["gps", "wifi", "cellular"]

_DEVICE_STATUS_OPTIONS = [*DEVICE_STATUS_CODES.values(), "error"]

_BATTERY_STATUS = {
    "Charging": "charging",
    "Full": "full",
    "NotCharging": "not_charging",
}

_LOCATION_TYPES = {
    "GPS": "gps",
    "Wifi": "wifi",
    "Cell": "cellular",
    "Cellular": "cellular",
}


def _battery_icon(device: IcloudDevice) -> str:
    """Return the battery icon for the device."""
    return icon_for_battery_level(
        battery_level=device.battery_level,
        charging=device.battery_status == "Charging",
    )


def _battery_status(device: IcloudDevice) -> str | None:
    """Return the normalized charging status of the device."""
    if (status := device.battery_status) is None:
        return None
    return _BATTERY_STATUS.get(status)


def _location_type(device: IcloudDevice) -> str | None:
    """Return the normalized type of the last location fix."""
    if (location_type := device.location_type) is None:
        return None
    return _LOCATION_TYPES.get(location_type)


@dataclass(frozen=True, kw_only=True)
class IcloudSensorEntityDescription(SensorEntityDescription):
    """Describes an iCloud sensor."""

    value_fn: Callable[[IcloudDevice], Any]
    icon_fn: Callable[[IcloudDevice], str] | None = None
    supported_fn: Callable[[IcloudDevice], bool] | None = None
    legacy_attributes: bool = False


SENSORS: tuple[IcloudSensorEntityDescription, ...] = (
    IcloudSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        # The battery sensor carried the device attributes before the dedicated
        # sensors exposed them, so it keeps them for backwards compatibility.
        legacy_attributes=True,
        value_fn=lambda device: device.battery_level,
        icon_fn=_battery_icon,
        supported_fn=lambda device: device.battery_level is not None,
    ),
    IcloudSensorEntityDescription(
        key="battery_status",
        translation_key="battery_status",
        device_class=SensorDeviceClass.ENUM,
        options=BATTERY_STATUS_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_battery_status,
    ),
    IcloudSensorEntityDescription(
        key="device_status",
        translation_key="device_status",
        device_class=SensorDeviceClass.ENUM,
        options=_DEVICE_STATUS_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.device_status,
    ),
    IcloudSensorEntityDescription(
        key="owner",
        translation_key="owner",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.owner_name,
    ),
    IcloudSensorEntityDescription(
        key="last_location",
        translation_key="last_location",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.location_timestamp,
        supported_fn=lambda device: device.location_available,
    ),
    IcloudSensorEntityDescription(
        key="location_type",
        translation_key="location_type",
        device_class=SensorDeviceClass.ENUM,
        options=_LOCATION_TYPE_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_location_type,
        supported_fn=lambda device: device.location_available,
    ),
    IcloudSensorEntityDescription(
        key="location_accuracy",
        translation_key="location_accuracy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.location_accuracy,
        supported_fn=lambda device: device.location_available,
    ),
    IcloudSensorEntityDescription(
        key="altitude",
        translation_key="altitude",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.location_altitude,
        supported_fn=lambda device: device.location_available,
    ),
    IcloudSensorEntityDescription(
        key="floor_level",
        translation_key="floor_level",
        entity_category=EntityCategory.DIAGNOSTIC,
        # Apple only reports a floor for fixes inside mapped buildings.
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.location_floor_level,
        supported_fn=lambda device: device.location_available,
    ),
    IcloudSensorEntityDescription(
        key="last_locked",
        translation_key="last_locked",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.last_locked,
        supported_fn=lambda device: device.lock_available,
    ),
    IcloudSensorEntityDescription(
        key="last_lost",
        translation_key="last_lost",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.last_lost,
        supported_fn=lambda device: device.lost_mode_available,
    ),
    IcloudSensorEntityDescription(
        key="last_wiped",
        translation_key="last_wiped",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.last_wiped,
        supported_fn=lambda device: device.erase_available,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IcloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for iCloud devices."""
    account = entry.runtime_data
    tracked = set[str]()

    @callback
    def update_account() -> None:
        """Add sensors for devices that appeared since the last poll."""
        add_entities(account, async_add_entities, tracked)

    account.listeners.append(
        async_dispatcher_connect(hass, account.signal_device_new, update_account)
    )

    update_account()


@callback
def add_entities(
    account: IcloudAccount,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add sensors for devices that support them."""
    new_entities = []

    for dev_id, device in account.devices.items():
        for description in SENSORS:
            if f"{dev_id}_{description.key}" in tracked:
                continue
            if description.supported_fn is not None and not description.supported_fn(
                device
            ):
                continue

            new_entities.append(IcloudDeviceSensor(account, device, description))
            tracked.add(f"{dev_id}_{description.key}")

    async_add_entities(new_entities, True)


class IcloudDeviceSensor(IcloudDeviceEntity, SensorEntity):
    """Representation of an iCloud device sensor."""

    entity_description: IcloudSensorEntityDescription

    def __init__(
        self,
        account: IcloudAccount,
        device: IcloudDevice,
        description: IcloudSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(account, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.unique_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the sensor state."""
        return self.entity_description.value_fn(self._device)

    @property
    @override
    def icon(self) -> str | None:
        """Return the sensor icon."""
        if (icon_fn := self.entity_description.icon_fn) is not None:
            return icon_fn(self._device)
        return super().icon

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device attributes on the sensors that carried them."""
        if not self.entity_description.legacy_attributes:
            return None
        return self._device.extra_state_attributes
