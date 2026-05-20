"""Constants and protocol encoding for the KlikAanKlikUit (Kaku) RC integration."""

import importlib
import sys
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


def _import_kaku_command() -> type:
    """Import KakuCommand from rf-protocols >= 3.1.0.

    Home Assistant may preload rf_protocols 2.x from site-packages. Ensure the
    /config/deps location (where custom integration requirements are installed)
    is preferred, then reload rf_protocols modules.
    """
    deps_path = "/config/deps"
    if deps_path not in sys.path:
        sys.path.insert(0, deps_path)

    for module_name in (
        "rf_protocols.commands.kaku",
        "rf_protocols.commands",
        "rf_protocols",
    ):
        sys.modules.pop(module_name, None)

    return importlib.import_module("rf_protocols.commands.kaku").KakuCommand


KakuCommand = _import_kaku_command()


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

    command = KakuCommand(
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
