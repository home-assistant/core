"""Use serial protocol of Acer projector to obtain state of the projector."""
from __future__ import annotations

from typing import Final

from homeassistant.const import STATE_OFF, STATE_ON

CONF_WRITE_TIMEOUT: Final = "write_timeout"

DEFAULT_NAME: Final = "Acer Projector"
DEFAULT_TIMEOUT: Final = 1
DEFAULT_WRITE_TIMEOUT: Final = 1

ECO_MODE: Final = "ECO Mode"

ICON: Final = "mdi:projector"

INPUT_SOURCE: Final = "Input Source"

LAMP: Final = "Lamp"
LAMP_HOURS: Final = "Lamp Hours"

MODEL: Final = "Model"

# Commands known to the projector
CMD_DICT: Final[dict[str, str]] = {
    LAMP: "* 0 Lamp ?\r",
    LAMP_HOURS: "* 0 Lamp\r",
    INPUT_SOURCE: "* 0 Src ?\r",
    ECO_MODE: "* 0 IR 052\r",
    MODEL: "* 0 IR 035\r",
    STATE_ON: "* 0 IR 001\r",
    STATE_OFF: "* 0 IR 002\r",
}
