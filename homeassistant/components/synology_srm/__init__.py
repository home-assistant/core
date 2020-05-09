"""The Synology SRM integration."""
import asyncio

from synology_srm import Client as SynologyClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .router import SynologySrmRouter

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
PLATFORMS = ["device_tracker"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Synology SRM component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Synology SRM from a config entry."""
    client = get_srm_client_from_user_data(entry.data)
    router = SynologySrmRouter(hass, client)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = router

    await router.async_setup()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        router = hass.data[DOMAIN].pop(entry.unique_id)
        await router.async_unload()

    return unload_ok


def get_srm_client_from_user_data(data) -> SynologyClient:
    """Get the Synology SRM client from user data."""
    client = SynologyClient(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        https=data[CONF_SSL],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
    )

    if not data[CONF_VERIFY_SSL]:
        client.http.disable_https_verify()

    return client


def fetch_srm_device_id(client: SynologyClient):
    """Fetch the Synology SRM device ID from the user."""
    info = client.mesh.get_system_info()
    return info["nodes"][0]["unique"]
