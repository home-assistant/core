"""Constants for the GeoSphere Austria Warnings integration.

Warning data is provided by GeoSphere Austria (https://www.geosphere.at)
under the Creative Commons Attribution 4.0 license.
"""

from enum import StrEnum
import logging


class GeoSphereService(StrEnum):
    """Store keys for GeoSphere Austria Warnings services."""

    GET_WARNINGS = "get_warnings"


DOMAIN = "geosphere_austria_warnings"

LOGGER = logging.getLogger(__package__)

ATTRIBUTION = "Data provided by GeoSphere Austria"
MANUFACTURER = "GeoSphere Austria"
WARNINGS_URL = "https://warnungen.zamg.at/"
