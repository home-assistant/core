"""Storage for remote scanners."""

from typing import TypedDict

from habluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    BluetoothServiceInfoBleak,
    DiscoveredDeviceAdvertisementData,
    DiscoveredDeviceAdvertisementDataDict,
    DiscoveryStorageType,
    discovered_device_advertisement_data_from_dict,
    discovered_device_advertisement_data_to_dict,
    expire_stale_scanner_discovered_device_advertisement_data,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

REMOTE_SCANNER_STORAGE_VERSION = 1
REMOTE_SCANNER_STORAGE_KEY = "bluetooth.remote_scanners"
EVENT_DRIVEN_STORAGE_VERSION = 1
EVENT_DRIVEN_STORAGE_KEY = "bluetooth.event_driven_history"
SCANNER_SAVE_DELAY = 5


class EventDrivenSourceDict(TypedDict):
    """Where the stored advertisement of an event-driven address came from."""

    source: str
    connectable: bool


class EventDrivenHistoryDict(TypedDict):
    """The accepted advertisements of event-driven addresses."""

    sources: dict[str, EventDrivenSourceDict]
    advertisements: DiscoveredDeviceAdvertisementDataDict


def _event_driven_history_to_dict(
    history: dict[str, BluetoothServiceInfoBleak],
) -> EventDrivenHistoryDict:
    """Serialize the accepted advertisements of event-driven addresses."""
    return EventDrivenHistoryDict(
        sources={
            address: EventDrivenSourceDict(
                source=info.source, connectable=info.connectable
            )
            for address, info in history.items()
        },
        advertisements=discovered_device_advertisement_data_to_dict(
            DiscoveredDeviceAdvertisementData(
                connectable=False,
                expire_seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
                discovered_device_advertisement_datas={
                    address: (info.device, info.advertisement)
                    for address, info in history.items()
                },
                discovered_device_timestamps={
                    address: info.time for address, info in history.items()
                },
            )
        ),
    )


def _event_driven_history_from_dict(
    data: EventDrivenHistoryDict,
) -> dict[str, BluetoothServiceInfoBleak]:
    """Deserialize the accepted advertisements, which don't expire."""
    if not (
        loaded := discovered_device_advertisement_data_from_dict(data["advertisements"])
    ):
        return {}
    sources = data["sources"]
    return {
        address: BluetoothServiceInfoBleak.from_device_and_advertisement_data(
            device,
            advertisement_data,
            sources[address]["source"],
            loaded.discovered_device_timestamps[address],
            sources[address]["connectable"],
        )
        for address, (
            device,
            advertisement_data,
        ) in loaded.discovered_device_advertisement_datas.items()
    }


class BluetoothStorage:
    """Storage for remote scanners."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the storage."""
        self._store: Store[DiscoveryStorageType] = Store(
            hass, REMOTE_SCANNER_STORAGE_VERSION, REMOTE_SCANNER_STORAGE_KEY
        )
        self._data: DiscoveryStorageType = {}
        self._event_driven_store: Store[EventDrivenHistoryDict] = Store(
            hass, EVENT_DRIVEN_STORAGE_VERSION, EVENT_DRIVEN_STORAGE_KEY
        )
        self._event_driven_history: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_setup(self) -> None:
        """Set up the storage."""
        self._data = await self._store.async_load() or {}
        expire_stale_scanner_discovered_device_advertisement_data(self._data)
        if event_driven_data := await self._event_driven_store.async_load():
            self._event_driven_history = _event_driven_history_from_dict(
                event_driven_data
            )
            # Outdated after a crash, a clean stop saves it again
            await self._event_driven_store.async_remove()

    def scanners(self) -> list[str]:
        """Get all scanners."""
        return list(self._data.keys())

    @callback
    def async_remove_advertisement_history(self, scanner: str) -> None:
        """Remove discovered devices by scanner."""
        if self._data.pop(scanner, None):
            self._store.async_delay_save(self._async_get_data, SCANNER_SAVE_DELAY)

    @callback
    def async_get_advertisement_history(
        self, scanner: str
    ) -> DiscoveredDeviceAdvertisementData | None:
        """Get discovered devices by scanner."""
        if not (scanner_data := self._data.get(scanner)):
            return None
        return discovered_device_advertisement_data_from_dict(scanner_data)

    @callback
    def async_get_advertisement_history_as_dict(
        self, scanner: str
    ) -> DiscoveredDeviceAdvertisementDataDict | None:
        """Get discovered devices by scanner as a dict."""
        return self._data.get(scanner)

    @callback
    def _async_get_data(self) -> DiscoveryStorageType:
        """Get data to save to disk."""
        return self._data

    @callback
    def async_set_advertisement_history(
        self, scanner: str, data: DiscoveredDeviceAdvertisementData
    ) -> None:
        """Set discovered devices by scanner."""
        self._data[scanner] = discovered_device_advertisement_data_to_dict(data)
        self._store.async_delay_save(self._async_get_data, SCANNER_SAVE_DELAY)

    @callback
    def async_get_event_driven_history(self) -> dict[str, BluetoothServiceInfoBleak]:
        """Get the stored accepted advertisements of event-driven addresses."""
        return self._event_driven_history

    @callback
    def async_set_event_driven_history(
        self, history: dict[str, BluetoothServiceInfoBleak]
    ) -> None:
        """Store the accepted advertisements of event-driven addresses."""
        data = _event_driven_history_to_dict(history)
        self._event_driven_store.async_delay_save(lambda: data, SCANNER_SAVE_DELAY)
