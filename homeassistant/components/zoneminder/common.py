"""Common code for the ZoneMinder component."""
from enum import Enum
from typing import List

import requests
from zoneminder.zm import ZoneMinder

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from . import const


def prime_domain_data(hass: HomeAssistant) -> None:
    """Prime the data structures."""
    hass.data.setdefault(const.DOMAIN, {})


def prime_platform_configs(hass: HomeAssistant, domain: str) -> None:
    """Prime the data structures."""
    prime_domain_data(hass)
    hass.data[const.DOMAIN].setdefault(const.PLATFORM_CONFIGS, {})
    hass.data[const.DOMAIN][const.PLATFORM_CONFIGS].setdefault(domain, [])


def set_platform_configs(hass: HomeAssistant, domain: str, configs: List[dict]) -> None:
    """Set platform configs."""
    prime_platform_configs(hass, domain)
    hass.data[const.DOMAIN][const.PLATFORM_CONFIGS][domain] = configs


def get_platform_configs(hass: HomeAssistant, domain: str) -> List[dict]:
    """Get platform configs."""
    prime_platform_configs(hass, domain)
    return hass.data[const.DOMAIN][const.PLATFORM_CONFIGS][domain]


def prime_config_data(hass: HomeAssistant, unique_id: str) -> None:
    """Prime the data structures."""
    prime_domain_data(hass)
    hass.data[const.DOMAIN].setdefault(const.CONFIG_DATA, {})
    hass.data[const.DOMAIN][const.CONFIG_DATA].setdefault(unique_id, {})


def set_client_to_data(hass: HomeAssistant, unique_id: str, client: ZoneMinder) -> None:
    """Put a ZoneMinder client in the Home Assistant data."""
    prime_config_data(hass, unique_id)
    hass.data[const.DOMAIN][const.CONFIG_DATA][unique_id][const.API_CLIENT] = client


def is_client_in_data(hass: HomeAssistant, unique_id: str) -> bool:
    """Check if ZoneMinder client is in the Home Assistant data."""
    prime_config_data(hass, unique_id)
    return const.API_CLIENT in hass.data[const.DOMAIN][const.CONFIG_DATA][unique_id]


def get_client_from_data(hass: HomeAssistant, unique_id: str) -> ZoneMinder:
    """Get a ZoneMinder client from the Home Assistant data."""
    prime_config_data(hass, unique_id)
    return hass.data[const.DOMAIN][const.CONFIG_DATA][unique_id][const.API_CLIENT]


def del_client_from_data(hass: HomeAssistant, unique_id: str) -> None:
    """Delete a ZoneMinder client from the Home Assistant data."""
    prime_config_data(hass, unique_id)
    del hass.data[const.DOMAIN][const.CONFIG_DATA][unique_id][const.API_CLIENT]


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
        conf.get(const.CONF_PATH_ZMS),
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
