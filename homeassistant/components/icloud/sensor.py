"""Support for iCloud sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .account import IcloudAccount, IcloudConfigEntry, IcloudDevice
from .const import DEVICE_STATUS_CODES, DOMAIN
from .coordinator import IcloudStorageCoordinator, IcloudStorageData
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
    _async_setup_storage(entry, async_add_entities)
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


@dataclass(frozen=True, kw_only=True)
class IcloudStorageSensorDescription(SensorEntityDescription):
    """Describe an account storage sensor."""

    value_fn: Callable[[IcloudStorageData], int | float | None]


STORAGE_SENSORS = (
    IcloudStorageSensorDescription(
        key="total",
        translation_key="storage_total",
        value_fn=lambda data: data.total,
    ),
    IcloudStorageSensorDescription(
        key="used",
        translation_key="storage_used",
        value_fn=lambda data: data.used,
    ),
    IcloudStorageSensorDescription(
        key="free",
        translation_key="storage_free",
        value_fn=lambda data: data.free,
    ),
    IcloudStorageSensorDescription(
        key="percentage",
        translation_key="storage_percentage",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.percentage,
    ),
)

STORAGE_MEDIA = {"photos", "backup", "docs", "mail", "messages"}


def _storage_media_value(data: IcloudStorageData, *, key: str) -> int | None:
    """Return a category value if it is still present in the latest snapshot."""
    return data.media.get(key)


@callback
def _async_setup_storage(
    entry: IcloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up account storage and discover categories on subsequent refreshes."""
    coordinator = entry.runtime_data.storage_coordinator
    if TYPE_CHECKING:
        assert coordinator is not None
    async_add_entities(
        IcloudStorageSensor(coordinator, entry, description)
        for description in STORAGE_SENSORS
    )
    known: set[str] = set()

    @callback
    def add_media() -> None:
        """Add sensors for storage categories first reported by Apple."""
        if coordinator.data is None:
            return
        entities = []
        for key in coordinator.data.media.keys() - known:
            description = IcloudStorageSensorDescription(
                key=f"media_{key}",
                translation_key=(
                    f"storage_{key}" if key in STORAGE_MEDIA else "storage_media"
                ),
                translation_placeholders={"name": coordinator.data.labels[key]},
                value_fn=partial(_storage_media_value, key=key),
            )
            entities.append(IcloudStorageSensor(coordinator, entry, description))
            known.add(key)
        async_add_entities(entities)

    add_media()
    entry.async_on_unload(coordinator.async_add_listener(add_media))


class IcloudStorageSensor(CoordinatorEntity[IcloudStorageCoordinator], SensorEntity):
    """Account storage usage reported by iCloud."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    entity_description: IcloudStorageSensorDescription

    def __init__(
        self,
        coordinator: IcloudStorageCoordinator,
        entry: IcloudConfigEntry,
        description: IcloudStorageSensorDescription,
    ) -> None:
        """Initialize the storage sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_storage_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}_account")},
            manufacturer="Apple",
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )
        if description.native_unit_of_measurement != PERCENTAGE:
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = UnitOfInformation.BYTES
            self._attr_suggested_unit_of_measurement = UnitOfInformation.GIGABYTES

    @property
    @override
    def available(self) -> bool:
        """Return whether a successful storage snapshot is available."""
        return super().available and self.coordinator.data is not None

    @property
    @override
    def native_value(self) -> int | float | None:
        """Return usage from the current snapshot."""
        if (data := self.coordinator.data) is None:
            return None
        return self.entity_description.value_fn(data)
