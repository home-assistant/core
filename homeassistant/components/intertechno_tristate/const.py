"""Constants and helpers for the Intertechno TriState integration."""

from typing import Final

DOMAIN: Final = "intertechno_tristate"

CONF_TRANSMITTER: Final = "transmitter"
CONF_HOUSECODE: Final = "housecode"
CONF_CHANNEL: Final = "channel"
CONF_GROUP: Final = "group"
REPEAT_COUNT_LEARN: Final = 10
VALID_HOUSECODES: Final = tuple("ABCDEFGHIJKLMNOP")
MIN_GROUP: Final = 1
MAX_GROUP: Final = 4
MIN_CHANNEL: Final = 1
MAX_CHANNEL: Final = 4


def format_device_summary(housecode: str, group: int, channel: int) -> str:
    """Return a concise summary string for the configured device."""
    return f"HC {housecode} G {group} CH {channel}"


def encode_tristate_data(
    *,
    housecode: str,
    group: int,
    channel: int,
    on: bool,
) -> str:
    """Encode device settings and command state into a 12-symbol tristate payload."""
    normalized_housecode = housecode.upper()
    if normalized_housecode not in VALID_HOUSECODES:
        raise ValueError("housecode must be in [A-P]")
    if not (MIN_GROUP <= group <= MAX_GROUP):
        raise ValueError(f"group must be in [{MIN_GROUP}, {MAX_GROUP}]")
    if not (MIN_CHANNEL <= channel <= MAX_CHANNEL):
        raise ValueError(f"channel must be in [{MIN_CHANNEL}, {MAX_CHANNEL}]")

    def _encode_bits_lsb(value: int, bit_count: int) -> str:
        """Encode integer bits least-significant-bit first using 0/F symbols."""
        return "".join("F" if (value >> bit) & 1 else "0" for bit in range(bit_count))

    house_index = VALID_HOUSECODES.index(normalized_housecode)
    channel_index = channel - 1
    group_index = group - 1

    # Layout (12 symbols total): house(4) + channel(2) + group(2) + fixed(0F) + state(2)
    state = "FF" if on else "F0"
    return (
        _encode_bits_lsb(house_index, 4)
        + _encode_bits_lsb(channel_index, 2)
        + _encode_bits_lsb(group_index, 2)
        + "0F"
        + state
    )
