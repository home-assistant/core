"""Constants for the Netio switch component."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import CONF_HOST

ATTR_START_DATE: Final = "start_date"
ATTR_TOTAL_CONSUMPTION_KWH: Final = "total_energy_kwh"

CONF_OUTLETS: Final = "outlets"

DEFAULT_PORT: Final = 1234
DEFAULT_USERNAME: Final = "admin"

MIN_TIME_BETWEEN_SCANS: Final = timedelta(seconds=10)

REQ_CONF: Final[list[str]] = [CONF_HOST, CONF_OUTLETS]

URL_API_NETIO_EP: Final = "/api/netio/{host}"
