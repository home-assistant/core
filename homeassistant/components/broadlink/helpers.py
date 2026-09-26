"""Helper functions for the Broadlink integration."""

from base64 import b64decode

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN


def data_packet(value):
    """Decode a data packet given for a Broadlink remote."""
    value = cv.string(value)
    extra = len(value) % 4
    if extra > 0:
        value = value + ("=" * (4 - extra))
    return b64decode(value)


# RM4 Pro RF packets: type (0xB1), repeat, payload length (LE), carrier in kHz (LE),
# then durations alternating carrier on/off, starting with carrier on.
RF_PACKET_TYPE_RM4 = 0xB1
_RF_RM4_HEADER_LEN = 8
# Durations are in 32.84 us ticks; 100 ticks (~3.3 ms) is longer than any data
# pulse and shorter than the sync gap between repeated frames.
_RF_LONG_GAP_TICKS = 100


def fix_rf_packet_alignment(packet: bytes) -> bytes:
    """Drop a leading partial duration from a learned RM4 Pro RF packet.

    The RM4 Pro sometimes starts recording in the middle of a pulse, which
    shifts every duration by one slot. Replayed as is, the device transmits
    during the gaps between frames and receivers ignore it. In a correctly
    aligned packet the long gaps sit on carrier-off (odd) slots, so if every
    long gap sits on a carrier-on (even) slot, the first duration is dropped.
    """
    if len(packet) <= _RF_RM4_HEADER_LEN or packet[0] != RF_PACKET_TYPE_RM4:
        return packet

    end = min(4 + int.from_bytes(packet[2:4], "little"), len(packet))
    offsets = []
    gaps = []
    idx = _RF_RM4_HEADER_LEN
    while idx < end:
        offsets.append(idx)
        ticks = packet[idx]
        idx += 1
        if ticks == 0:
            if idx + 2 > end:
                return packet
            ticks = int.from_bytes(packet[idx : idx + 2], "big")
            idx += 2
        if ticks >= _RF_LONG_GAP_TICKS:
            gaps.append(len(offsets) - 1)

    if len(gaps) < 2 or any(slot % 2 for slot in gaps):
        return packet

    drop = offsets[1] - offsets[0]
    fixed = bytearray(packet[: offsets[0]] + packet[offsets[1] :])
    fixed[2:4] = (int.from_bytes(packet[2:4], "little") - drop).to_bytes(2, "little")
    return bytes(fixed)


def mac_address(mac):
    """Validate and convert a MAC address to bytes."""
    mac = cv.string(mac)
    if len(mac) == 17:
        mac = "".join(mac[i : i + 2] for i in range(0, 17, 3))
    elif len(mac) == 14:
        mac = "".join(mac[i : i + 4] for i in range(0, 14, 5))
    elif len(mac) != 12:
        raise ValueError("Invalid MAC address")
    return bytes.fromhex(mac)


def format_mac(mac):
    """Format a MAC address."""
    return ":".join([format(octet, "02x") for octet in mac])


def import_device(hass, host):
    """Create a config flow for a device."""
    configured_hosts = {
        entry.data.get(CONF_HOST) for entry in hass.config_entries.async_entries(DOMAIN)
    }

    if host not in configured_hosts:
        task = hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: host},
        )
        hass.async_create_task(task)
