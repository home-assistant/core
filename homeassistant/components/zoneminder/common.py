"""Common code for the ZoneMinder component."""
from enum import Enum

import requests
from zoneminder.zm import ZoneMinder

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from .const import CONF_PATH_ZMS, DOMAIN


def set_client_to_data(
    hass: HomeAssistant, config_entry: ConfigEntry, client: ZoneMinder
) -> None:
    """Put a ZoneMinder client in the Home Assistant data."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.unique_id] = client


def is_client_in_data(hass: HomeAssistant, unique_id: str) -> bool:
    """Check if ZoneMinder client is in the Home Assistant data."""
    hass.data.setdefault(DOMAIN, {})
    return unique_id in hass.data[DOMAIN]


def get_client_from_data(hass: HomeAssistant, unique_id: str) -> ZoneMinder:
    """Get a ZoneMinder client from the Home Assistant data."""
    hass.data.setdefault(DOMAIN, {})
    return hass.data[DOMAIN][unique_id]


def del_client_from_data(hass: HomeAssistant, unique_id: str) -> None:
    """Delete a ZoneMinder client from the Home Assistant data."""
    hass.data.setdefault(DOMAIN, {})
    del hass.data[DOMAIN][unique_id]


def create_client_from_config(conf: dict) -> ZoneMinder:
    """Create a new ZoneMinder client from a config."""
    protocol = "https" if conf[CONF_SSL] else "http"

    host_name = conf[CONF_HOST]
    server_origin = f"{protocol}://{host_name}"

    return ZoneMinder(
        server_origin,
        conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD),
        conf.get(CONF_PATH),
        conf.get(CONF_PATH_ZMS),
        conf.get(CONF_VERIFY_SSL),
    )


class ClientAvailabilityResult(Enum):
    """Client availability test result."""

    AVAILABLE = "available"
    ERROR_AUTH_FAIL = "auth_fail"
    ERROR_CONNECTION_ERROR = "connection_error"


async def async_test_client_availability(
    hass: HomeAssistant, client: ZoneMinder
) -> ClientAvailabilityResult:
    """Test the availability of a ZoneMinder client."""
    try:
        if await hass.async_add_job(client.login):
            return ClientAvailabilityResult.AVAILABLE
        return ClientAvailabilityResult.ERROR_AUTH_FAIL
    except requests.exceptions.ConnectionError:
        return ClientAvailabilityResult.ERROR_CONNECTION_ERROR
