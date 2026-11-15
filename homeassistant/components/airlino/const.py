"""Constants for the AirLino integration."""

from datetime import timedelta
import logging

DOMAIN = "airlino"
CONF_SETUP_VERIFIED = "setup_verified"

VALID_MODELS = {
    "AirLino pro",
    "AirLino",
    "AirLino plus",
    "Airlino max",
}

MIN_API_VERSION = "v19"


def api_version_number(api_version: str) -> int | None:
    """Return the numeric API version, if valid."""
    if not api_version.startswith("v"):
        return None
    try:
        return int(api_version[1:])
    except ValueError:
        return None


def is_supported_api_version(api_version: str) -> bool:
    """Return whether the API version is supported by the integration."""
    version = api_version_number(api_version)
    minimum_version = api_version_number(MIN_API_VERSION)
    return (
        version is not None
        and minimum_version is not None
        and version >= minimum_version
    )


UPDATE_INTERVAL = timedelta(seconds=10)

LOGGER = logging.getLogger(__package__)
