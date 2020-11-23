"""Support for services the qBittorrent API."""
import logging
import voluptuous as vol

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException

from homeassistant.helpers.dispatcher import async_dispatcher_send

from homeassistant.helpers.entity import Entity

from .const import (
    DATA_KEY_CLIENT,
    DATA_KEY_NAME,
    DOMAIN,
    SERVICE_ADD_DOWNLOAD,
    SERVICE_REMOVE_DOWNLOAD,
)
from .wrapper_functions import get_main_data_client, retrieve_torrentdata, create_client

DOWNLOAD_SCHEMA = vol.Schema(
    {
        vol.Optional("download_path"): str,
        vol.Required("server_url"): str,
        vol.Required("magnet_link"): str,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass):
    """Set up services for the QBittorrent component."""

    async def async_add_download_service(service_call):
        await hass.async_add_executor_job(add_download, hass, service_call)

    async def async_remove_download_service(service_call):
        await hass.async_add_executor_job(remove_download, hass, service_call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_DOWNLOAD,
        async_add_download_service,
        schema=DOWNLOAD_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_DOWNLOAD, async_remove_download_service
    )

    return True


def add_download(hass, service_call):
    qbit_data = hass.data[DOMAIN][service_call["server_url"]]
    return True


def remove_download(hass, service_call):
    return True