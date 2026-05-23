"""Constants and protocol encoding for the KlikAanKlikUit (Kaku) RC integration."""

from importlib import import_module
from typing import Final

DOMAIN: Final = "kaku_rc"

CONF_TRANSMITTER: Final = "transmitter"
CONF_DEVICE_ID: Final = "device_id"
CONF_CHANNEL: Final = "channel"
CONF_GROUP: Final = "group"
CONF_DIM: Final = "dim"

# Kaku self-learning protocol parameters
FREQUENCY_HZ: Final = 433_920_000
REPEAT_COUNT: Final = 4
REPEAT_COUNT_LEARN: Final = 10  # Higher repeats for learning/pairing
TIMEBASE_US: Final = 275  # Symbol time in microseconds (T = 275 µs)


def get_kaku_timings(
    device_id: int,
    channel: int,
    *,
    group: bool,
    on: bool | None = None,
    dimlevel: int | None = None,
    frame_repeats: int = REPEAT_COUNT,
) -> list[int]:
    """Get OOK timings for a Kaku command using rf-protocols library.

    Args:
        device_id: Device ID (0-67108863)
        channel: Channel/unit (1-16)
        group: Group command flag
        on: On/off state (None if using dimlevel)
        dimlevel: Brightness level 0-100 (None if using on/off)
        frame_repeats: Number of frame repeats

    Returns:
        List of OOK timings in microseconds
    """
    if (on is None) == (dimlevel is None):
        raise ValueError("provide exactly one of 'on' or 'dimlevel'")

    kaku_command = import_module("rf_protocols.commands.kaku").KakuCommand
    command = kaku_command(
        id=device_id,
        group=group,
        channel=channel,
        on=on,
        dimlevel=dimlevel,
        frame_repeats=frame_repeats,
        frequency=FREQUENCY_HZ,
        timebase_us=TIMEBASE_US,
    )
    return command.get_raw_timings()


def format_device_summary(device_id: int, channel: int, group: bool, dim: bool) -> str:
    """Return a concise summary string for the configured device."""
    group_text = "on" if group else "off"
    dim_text = "on" if dim else "off"
    return f"ID {device_id} CH {channel} Group {group_text} Brightness {dim_text}"
