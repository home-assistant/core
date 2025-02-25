"""const."""

from __future__ import annotations

from logging import Logger, getLogger

_LOGGER: Logger = getLogger(__package__)

DISCOVERY_TIMEOUT = 8
UPDATE_INTERVAL = "update_interval"

DOMAIN = "meross_scan"

MAX_ERRORS = 4

# Energy monitoring
SENSOR_EM = "em"

CHANNEL_DISPLAY_NAME: dict[str, dict[int, str]] = {
    "em06": {
        1: "A1",
        2: "B1",
        3: "C1",
        4: "A2",
        5: "B2",
        6: "C2",
    },
    "em16": {
        1: "A1",
        2: "A2",
        3: "A3",
        4: "A4",
        5: "A5",
        6: "A6",
        7: "B1",
        8: "B2",
        9: "B3",
        10: "B4",
        11: "B5",
        12: "B6",
        13: "C1",
        14: "C2",
        15: "C3",
        16: "C4",
        17: "C5",
        18: "C6",
    },
}
