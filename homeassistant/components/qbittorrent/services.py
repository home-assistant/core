"""Support for services the qBittorrent API."""
import logging

import voluptuous as vol

from .const import (
    DATA_KEY_CLIENT,
    DOMAIN,
    SERVICE_ADD_DOWNLOAD,
    SERVICE_REMOVE_DOWNLOAD,
)

DOWNLOAD_SCHEMA = vol.Schema(
    {
        vol.Optional("download_path"): str,
        vol.Optional("server_url"): str,
        vol.Required("magnet_link"): str,
    }
)

REMOVE_SCHEMA = vol.Schema(
    {
        vol.Optional("server_url"): str,
        vol.Required("torrent_hash"): str,
        vol.Optional("delete_permanent"): bool,
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
        DOMAIN,
        SERVICE_REMOVE_DOWNLOAD,
        async_remove_download_service,
        schema=REMOVE_SCHEMA,
    )

    return True


def add_download(hass, service_call):
    """Download a magnetlink."""
    qbit_url = service_call.data.get("server_url")
    download_path = service_call.data.get("download_path")
    magnet = service_call.data.get("magnet_link")
    client = get_qbitclient(hass, qbit_url)[DATA_KEY_CLIENT]

    client.download_from_link(magnet, savepath=download_path)
    return True


def get_qbitclient(hass, server_url=None):
    """Retrieve a configured qbittorrent clients by name."""
    qbittdata = hass.data[DOMAIN].values()

    if server_url:
        plex_server = next(
            (x for x in qbittdata if x.friendly_name == server_url), None
        )
        if plex_server is not None:
            return plex_server
        _LOGGER.error(
            "Requested Qbitclient '%s' not found in %s",
            server_url,
            [x.friendly_name for x in server_url],
        )
        return None

    if len(qbittdata) == 1:
        return next(iter(qbittdata))

    _LOGGER.error(
        "Multiple Qbittorrent clients configured, choose with 'server_url' key: %s",
        [x.friendly_name for x in qbittdata],
    )
    return None


def remove_download(hass, service_call):
    """Remove a download from the download/seed list."""
    qbit_url = service_call.data.get("server_url")
    torrent_hash = service_call.data.get("torrent_hash")
    delete_permanent = service_call.data.get("delete_permanent")
    if delete_permanent is None:
        delete_permanent = False

    client = get_qbitclient(hass, qbit_url)[DATA_KEY_CLIENT]

    if delete_permanent is True:
        client.delete_permanently(torrent_hash)
    else:
        client.delete(torrent_hash)
    return True
