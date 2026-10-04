"""Adds constants for SQL integration."""

import re
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .models import SQLData

DOMAIN = "sql"

# One SQLData holds the shared session makers and the shutdown listener for
# every config entry, so it is shared rather than owned by any one entry.
DOMAIN_DATA: HassKey[SQLData] = HassKey(DOMAIN)

PLATFORMS = [Platform.SENSOR]

CONF_COLUMN_NAME = "column"
CONF_QUERY = "query"
CONF_ADDITIONAL_OPTIONS = "additional_options"
DB_URL_RE = re.compile("//.*:.*@")
