"""Support for iCloud binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .account import IcloudAccount, IcloudConfigEntry, IcloudDevice
from .entity import IcloudDeviceEntity


@dataclass(frozen=True, kw_only=True)
class IcloudBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an iCloud binary sensor."""

    value_fn: Callable[[IcloudDevice], bool]
    supported_fn: Callable[[IcloudDevice], bool] | None = None


BINARY_SENSORS: tuple[IcloudBinarySensorEntityDescription, ...] = (
    IcloudBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda device: device.is_online,
    ),
    IcloudBinarySensorEntityDescription(
        key="lost_mode",
        translation_key="lost_mode",
        value_fn=lambda device: device.lost_mode_enabled,
        supported_fn=lambda device: device.lost_mode_available,
    ),
    IcloudBinarySensorEntityDescription(
        key="low_power_mode",
        translation_key="low_power_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.low_power_mode,
    ),
    IcloudBinarySensorEntityDescription(
        key="activation_lock",
        translation_key="activation_lock",
        device_class=BinarySensorDeviceClass.LOCK,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.activation_locked,
        supported_fn=lambda device: device.lock_available,
    ),
    IcloudBinarySensorEntityDescription(
        key="locating",
        translation_key="locating",
        entity_category=EntityCategory.DIAGNOSTIC,
        # Apple reports a device as locating while a locate is in flight, which
        # is most of the time for an integration that locates on every poll.
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.is_locating,
    ),
    IcloudBinarySensorEntityDescription(
        key="location_services",
        translation_key="location_services",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.location_services_enabled,
    ),
    # A problem binary sensor reads "Problem" when it is on, so these report the
    # raw Apple flag while their name describes the healthy state.
    IcloudBinarySensorEntityDescription(
        key="location_current",
        translation_key="location_current",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.location_is_old,
        supported_fn=lambda device: device.location_available,
    ),
    IcloudBinarySensorEntityDescription(
        key="location_accurate",
        translation_key="location_accurate",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.location_is_inaccurate,
        supported_fn=lambda device: device.location_available,
    ),
    IcloudBinarySensorEntityDescription(
        key="wipe_in_progress",
        translation_key="wipe_in_progress",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.wipe_in_progress,
        supported_fn=lambda device: device.erase_available,
    ),
    IcloudBinarySensorEntityDescription(
        key="remote_lock",
        translation_key="remote_lock",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.remote_lock_pending,
        supported_fn=lambda device: device.lock_available,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IcloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for iCloud devices."""
    account = entry.runtime_data
    tracked = set[str]()

    @callback
    def update_account() -> None:
        """Add binary sensors for devices that appeared since the last poll."""
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
    """Add binary sensors for devices that support them."""
    new_entities = []

    for dev_id, device in account.devices.items():
        for description in BINARY_SENSORS:
            if f"{dev_id}_{description.key}" in tracked:
                continue
            if description.supported_fn is not None and not description.supported_fn(
                device
            ):
                continue

            new_entities.append(IcloudDeviceBinarySensor(account, device, description))
            tracked.add(f"{dev_id}_{description.key}")

    async_add_entities(new_entities)


class IcloudDeviceBinarySensor(IcloudDeviceEntity, BinarySensorEntity):
    """Representation of an iCloud device binary sensor."""

    entity_description: IcloudBinarySensorEntityDescription

    def __init__(
        self,
        account: IcloudAccount,
        device: IcloudDevice,
        description: IcloudBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(account, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.unique_id}_{description.key}"

    @property
    @override
    def is_on(self) -> bool:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self._device)
