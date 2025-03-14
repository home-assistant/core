"""Support for iCloud sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level

from .account import IcloudAccount, IcloudDevice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
def add_entities(account, async_add_entities, tracked):
    """Add new tracker entities from the account."""
    new_tracked = []

    for dev_id, device in account.devices.items():
        if dev_id in tracked or device.battery_level is None:
            continue

        new_tracked.append(IcloudDeviceBatterySensor(account, device))
        tracked.add(dev_id)

    async_add_entities(new_tracked, True)


class IcloudDeviceBatterySensor(SensorEntity):
    """Representation of a iCloud device battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, account: IcloudAccount, device: IcloudDevice) -> None:
        """Initialize the battery sensor."""
        self._account = account
        self._device = device
        self._unsub_dispatcher: CALLBACK_TYPE | None = None
        self._attr_unique_id = f"{device.unique_id}_battery"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://icloud.com/",
            identifiers={(DOMAIN, device.unique_id)},
            manufacturer="Apple",
            model=device.device_model,
            name=device.name,
        )

    @property
    def native_value(self) -> int | None:
        """Battery state percentage."""
        return self._device.battery_level

    @property
    def icon(self) -> str:
        """Battery state icon handling."""
        return icon_for_battery_level(
            battery_level=self._device.battery_level,
            charging=self._device.battery_status == "Charging",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return default attributes for the iCloud device entity."""
        return self._device.extra_state_attributes

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, self._account.signal_device_update, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up after entity before removal."""
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
