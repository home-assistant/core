"""Support for tracking iBeacon devices."""

from ibeacon_ble import iBeaconAdvertisement

from homeassistant.components.device_tracker import BaseScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IBeaconConfigEntry
from .const import SIGNAL_IBEACON_DEVICE_NEW
from .coordinator import IBeaconCoordinator
from .entity import IBeaconEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IBeaconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for iBeacon Tracker component."""
    coordinator = entry.runtime_data

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


class IBeaconTrackerEntity(IBeaconEntity, BaseScannerEntity):
    """An iBeacon Tracker entity."""

    _attr_name = None
    _attr_source_type: SourceType = SourceType.BLUETOOTH_LE
    _attr_translation_key = "device_tracker"

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
    def is_connected(self) -> bool:
        """Return true if the device is connected."""
        return self._active

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
