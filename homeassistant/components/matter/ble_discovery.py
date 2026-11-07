"""Discovery of commissionable Matter devices over Bluetooth."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from struct import Struct
from typing import TYPE_CHECKING, Self

from bluetooth_data_tools import parse_advertisement_data

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

if TYPE_CHECKING:
    from home_assistant_bluetooth import BluetoothServiceInfoBleak

MATTER_BLE_SERVICE_DATA_UUID = "0000fff6-0000-1000-8000-00805f9b34fb"

# Matter devices advertise at most every 1.285 s while commissionable; this
# leaves margin for proxy batching before a discovery is considered stale.
STALE_ADVERTISEMENT_SECONDS = 60

_OPCODE_COMMISSIONABLE = 0x00
# Opcode, discriminator with version nibble, vendor id, product id, flags.
_COMMISSIONABLE = Struct("<BHHHB")


@dataclass(frozen=True, slots=True)
class MatterBleAdvertisement:
    """Decoded Matter commissionable advertisement (Matter Core spec 5.4.2.5.6)."""

    discriminator: int
    vendor_id: int
    product_id: int

    @property
    def unique_id(self) -> str:
        """Return the commissioning identity, which survives BLE address rotation.

        The advertisement carries nothing more specific, so identical products
        whose 12 bit discriminators collide share one discovery, as they do for
        commissioning itself.
        """
        return f"{self.vendor_id:04x}{self.product_id:04x}{self.discriminator:03x}"

    @classmethod
    def from_service_data(cls, data: bytes | None) -> Self | None:
        """Decode the service data payload."""
        if data is None or len(data) < _COMMISSIONABLE.size:
            return None
        opcode, discriminator, vendor_id, product_id, _flags = (
            _COMMISSIONABLE.unpack_from(data)
        )
        if opcode != _OPCODE_COMMISSIONABLE:
            return None
        return cls(
            discriminator=discriminator & 0x0FFF,
            vendor_id=vendor_id,
            product_id=product_id,
        )

    @classmethod
    def from_service_info(cls, service_info: BluetoothServiceInfoBleak) -> Self | None:
        """Decode from the service data aggregated across a device's packets."""
        return cls.from_service_data(
            service_info.service_data.get(MATTER_BLE_SERVICE_DATA_UUID)
        )

    @classmethod
    def from_raw(cls, raw: bytes) -> Self | None:
        """Decode from a single raw packet, ignoring data from earlier packets."""
        return cls.from_service_data(
            parse_advertisement_data((raw,)).service_data.get(
                MATTER_BLE_SERVICE_DATA_UUID
            )
        )


class MatterBleDiscovery:
    """A discovered device, watched until it stops advertising as commissionable."""

    def __init__(
        self,
        hass: HomeAssistant,
        advertisement: MatterBleAdvertisement,
        address: str,
        on_stale: Callable[[], None],
    ) -> None:
        """Initialize the discovery."""
        self._hass = hass
        self.advertisement = advertisement
        self._address = address
        self._on_stale = on_stale
        self._unsub: CALLBACK_TYPE | None = None
        self._stale_unsub: CALLBACK_TYPE | None = None

    @callback
    def async_start(self) -> None:
        """Start watching the device's advertisements."""
        # Imported lazily; bluetooth is only an after dependency of Matter.
        from homeassistant.components import bluetooth  # noqa: PLC0415

        self._unsub = bluetooth.async_register_advertisement_callback(
            self._hass, self._async_seen, self._address
        )
        self._async_schedule_stale()

    @callback
    def async_stop(self) -> None:
        """Stop watching the device's advertisements."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._stale_unsub is not None:
            self._stale_unsub()
            self._stale_unsub = None

    @callback
    def _async_schedule_stale(self) -> None:
        """Restart the window the device has to advertise in."""
        if self._stale_unsub is not None:
            self._stale_unsub()
        self._stale_unsub = async_call_later(
            self._hass, STALE_ADVERTISEMENT_SECONDS, self._async_stale
        )

    @callback
    def _async_seen(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Extend the window while the device advertises as commissionable."""
        # Service data is aggregated across packets, so only the packet itself
        # proves the device is still commissionable. Packets from a scanner that
        # reports no raw data cannot be checked and so prove nothing.
        if (raw := service_info.raw) is not None and MatterBleAdvertisement.from_raw(
            raw
        ):
            self._async_schedule_stale()

    @callback
    def _async_stale(self, _now: datetime) -> None:
        """Report the device as gone; it stopped advertising as commissionable."""
        from homeassistant.components import bluetooth  # noqa: PLC0415

        self.async_stop()
        # Drop the aggregated payload that still says the device is
        # commissionable, so the next advertisement decides on its own whether
        # this device is discovered again.
        bluetooth.async_clear_advertisement_history(self._hass, self._address)
        bluetooth.async_clear_address_from_match_history(self._hass, self._address)
        self._on_stale()
