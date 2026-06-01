"""Models helper class for the usb integration."""

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True, kw_only=True)
class SerialProxy:
    """A serial proxy exposed by an integration over the network.

    Serial proxies tunnel a serial connection to a device (for example an RF
    radio) that is attached to another Home Assistant-managed device, such as an
    ESPHome node. The ``device`` is the proxy address that can be opened with
    serialx (e.g. ``esphome-hass://...``).
    """

    device: str
    name: str
    config_entry_id: str
    device_id: str | None = None
    port_type: str | None = None
    entity_ids: list[str] = field(default_factory=list)
    supported_frequency_ranges: list[tuple[int, int]] = field(default_factory=list)


@dataclass(slots=True, frozen=True, kw_only=True)
class SerialDevice:
    """A serial device."""

    device: str
    serial_number: str | None
    manufacturer: str | None
    description: str | None
    interface_description: str | None = None
    interface_num: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class USBDevice(SerialDevice):
    """A usb device."""

    vid: str
    pid: str

    # bcdDevice descriptor, often the firmware revision
    bcd_device: int | None = None
