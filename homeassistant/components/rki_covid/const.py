"""Constants for the RKI Covid numbers integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "rki_covid"

ATTRIBUTION: Final = "Data provided by Robert Koch-Institut"
DEFAULT_SCAN_INTERVAL = 3  # hours

# configuration attributes
ATTR_COUNTY = "county"
