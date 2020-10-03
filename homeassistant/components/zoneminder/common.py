"""Common code for the ZoneMinder component."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

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


@dataclass
class ConfigData:
    """Data structure for holding config data in hass data."""

    config_entry: ConfigEntry
    client: ZoneMinder


def set_config_data(
    hass: HomeAssistant, config_entry: ConfigEntry, client: ZoneMinder
) -> None:
    """Put a ZoneMinder client in the Home Assistant data."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = ConfigData(
        config_entry=config_entry, client=client
    )


def get_config_data(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> Optional[ConfigData]:
    """Get config data from hass data."""
    return hass.data[DOMAIN][config_entry.entry_id]


def delete_config_data(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Delete config data from hass data."""
    del hass.data.get(DOMAIN, {})[config_entry.entry_id]


def get_config_data_for_host(hass: HomeAssistant, host: str) -> Optional[ConfigData]:
    """Get config data for a specific host name."""
    return next(
        iter(
            [
                config_data
                for config_data in hass.data.get(DOMAIN, {}).values()
                if config_data.config_entry.data[CONF_HOST] == host
            ]
        ),
        None,
    )


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
    ERROR_AUTH_FAIL = "invalid_auth"
    ERROR_CONNECTION_ERROR = "cannot_connect"


async def async_test_client_availability(
    hass: HomeAssistant, client: ZoneMinder
) -> ClientAvailabilityResult:
    """Test the availability of a ZoneMinder client."""
    try:
        if await hass.async_add_executor_job(client.login):
            return ClientAvailabilityResult.AVAILABLE
        return ClientAvailabilityResult.ERROR_AUTH_FAIL
    except requests.exceptions.ConnectionError:
        return ClientAvailabilityResult.ERROR_CONNECTION_ERROR
