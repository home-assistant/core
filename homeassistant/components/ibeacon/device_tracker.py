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

from .const import (
    ATTR_MAJOR,
    ATTR_MINOR,
    ATTR_RSSI_BY_ADDRESS,
    ATTR_UUID,
    DOMAIN,
    SIGNAL_IBEACON_DEVICE_NEW,
)
from .data import IBeaconCoordinator, signal_seen, signal_unavailable


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for iBeacon Tracker component."""
    ibeacon_coordinator: IBeaconCoordinator = hass.data[DOMAIN]

    @callback
    def _async_device_new(
        unique_id: str,
        name: str,
        parsed: iBeaconAdvertisement,
        rssi_by_address: dict[str, int],
    ) -> None:
        """Signal a new device."""
        async_add_entities(
            [
                IBeaconTrackerEntity(
                    ibeacon_coordinator, name, unique_id, parsed, rssi_by_address
                )
            ]
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_IBEACON_DEVICE_NEW, _async_device_new)
    )


class IBeaconTrackerEntity(BaseTrackerEntity):
    """An iBeacon Tracker entity."""

    _attr_should_poll = False

    def __init__(
        self,
        ibeacon_coordinator: IBeaconCoordinator,
        name: str,
        unique_id: str,
        parsed: iBeaconAdvertisement,
        rssi_by_address: dict[str, int],
    ) -> None:
        """Initialize an iBeacon tracker entity."""
        self._rssi_by_address = rssi_by_address
        self._ibeacon_coordinator = ibeacon_coordinator
        self._parsed = parsed
        self._attr_unique_id = unique_id
        self._active = True
        self._attr_name = name

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

    @property
    def extra_state_attributes(self) -> dict[str, str | int | dict[str, int]]:
        """Return the device state attributes."""
        return {
            ATTR_UUID: str(self._parsed.uuid),
            ATTR_MAJOR: self._parsed.major,
            ATTR_MINOR: self._parsed.minor,
            ATTR_RSSI_BY_ADDRESS: self._rssi_by_address,
        }

    @callback
    def _async_seen(
        self, parsed: iBeaconAdvertisement, rssi_by_address: dict[str, int]
    ) -> None:
        """Update state."""
        self._active = True
        self._parsed = parsed
        self._rssi_by_address = rssi_by_address
        self.async_write_ha_state()

    @callback
    def _async_unavailable(self) -> None:
        """Update state."""
        self._active = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callbacks."""
        assert self.unique_id is not None
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_seen(self.unique_id),
                self._async_seen,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_unavailable(self.unique_id),
                self._async_unavailable,
            )
        )
