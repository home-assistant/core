"""Support for tracking for iCloud devices."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .account import IcloudAccount, IcloudDevice
from .const import (
    DEVICE_LOCATION_HORIZONTAL_ACCURACY,
    DEVICE_LOCATION_LATITUDE,
    DEVICE_LOCATION_LONGITUDE,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for iCloud component."""
    account: IcloudAccount = hass.data[DOMAIN][entry.unique_id]
    tracked = set[str]()

    @callback
    def update_account():
        """Update the values of the account."""
        add_entities(account, async_add_entities, tracked)

    account.listeners.append(
        async_dispatcher_connect(hass, account.signal_device_new, update_account)
    )

    update_account()


@callback
def add_entities(account: IcloudAccount, async_add_entities, tracked):
    """Add new tracker entities from the account."""
    new_tracked = []

    for dev_id, device in account.devices.items():
        if dev_id in tracked or device.location is None:
            continue

        new_tracked.append(IcloudTrackerEntity(account, device))
        tracked.add(dev_id)

    async_add_entities(new_tracked, True)


class IcloudTrackerEntity(TrackerEntity):
    """Represent a tracked device."""

    def __init__(self, account: IcloudAccount, device: IcloudDevice) -> None:
        """Set up the iCloud tracker entity."""
        self._account = account
        self._device = device
        self._unsub_dispatcher: CALLBACK_TYPE | None = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device.unique_id

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name

    @property
    def location_accuracy(self):
        """Return the location accuracy of the device."""
        return self._device.location[DEVICE_LOCATION_HORIZONTAL_ACCURACY]

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._device.location[DEVICE_LOCATION_LATITUDE]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._device.location[DEVICE_LOCATION_LONGITUDE]

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device."""
        return self._device.battery_level

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def icon(self) -> str:
        """Return the icon."""
        return icon_for_icloud_device(self._device)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return self._device.extra_state_attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            configuration_url="https://icloud.com/",
            identifiers={(DOMAIN, self._device.unique_id)},
            manufacturer="Apple",
            model=self._device.device_model,
            name=self._device.name,
        )

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, self._account.signal_device_update, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up after entity before removal."""
        if self._unsub_dispatcher:
            self._unsub_dispatcher()


def icon_for_icloud_device(icloud_device: IcloudDevice) -> str:
    """Return an icon for the device."""
    switcher = {
        "iPad": "mdi:tablet",
        "iPhone": "mdi:cellphone",
        "iPod": "mdi:ipod",
        "iMac": "mdi:monitor",
        "MacBookPro": "mdi:laptop",
    }

    return switcher.get(icloud_device.device_class, "mdi:cellphone-link")
