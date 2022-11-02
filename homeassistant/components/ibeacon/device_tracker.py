"""Support for tracking iBeacon devices."""
from __future__ import annotations

from ibeacon_ble import iBeaconAdvertisement

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import BaseTrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_IBEACON_DEVICE_NEW
from .coordinator import IBeaconCoordinator
from .entity import IBeaconEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for iBeacon Tracker component."""
    coordinator: IBeaconCoordinator = hass.data[DOMAIN]

    @callback
    def _async_device_new(
        unique_id: str,
        identifier: str,
        ibeacon_advertisement: iBeaconAdvertisement,
    ) -> None:
        """Signal a new device."""
        async_add_entities(
            [
                IBeaconTrackerEntity(
                    coordinator,
                    identifier,
                    unique_id,
                    ibeacon_advertisement,
                )
            ]
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_IBEACON_DEVICE_NEW, _async_device_new)
    )


class IBeaconTrackerEntity(IBeaconEntity, BaseTrackerEntity):
    """An iBeacon Tracker entity."""

    def __init__(
        self,
        coordinator: IBeaconCoordinator,
        identifier: str,
        device_unique_id: str,
        ibeacon_advertisement: iBeaconAdvertisement,
    ) -> None:
        """Initialize an iBeacon tracker entity."""
        super().__init__(
            coordinator, identifier, device_unique_id, ibeacon_advertisement
        )
        self._attr_unique_id = device_unique_id
        self._active = True

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return STATE_HOME if self._active else STATE_NOT_HOME

    @property
    def source_type(self) -> SourceType:
        """Return tracker source type."""
        return SourceType.BLUETOOTH_LE

    @property
    def icon(self) -> str:
        """Return device icon."""
        return "mdi:bluetooth-connect" if self._active else "mdi:bluetooth-off"

    @callback
    def _async_seen(
        self,
        ibeacon_advertisement: iBeaconAdvertisement,
    ) -> None:
        """Update state."""
        self._active = True
        self._ibeacon_advertisement = ibeacon_advertisement
        self.async_write_ha_state()

    @callback
    def _async_unavailable(self) -> None:
        """Set unavailable."""
        self._active = False
        self.async_write_ha_state()
