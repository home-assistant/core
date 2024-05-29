# pylint: disable=fixme


"""Support for the Philips Hue system."""

# from came_domotic_unofficial import Auth, CameDomoticAPI
from came_domotic_unofficial.models import CameServerInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .came_domotic_server import CameDomoticServer
from .const import DEVICE_NAME, DOMAIN, MANUFACTURER

# from .services import async_register_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a CAME Domotic server instance from a config entry."""
    # check (and run) migrations if needed
    # await check_migration(hass, entry)

    # setup the server instance
    api: CameDomoticServer = CameDomoticServer(hass, entry)
    if not await api.async_initialize_api():
        return False

    # TODO choose whether to implement services or not
    # register CAME Domotic domain services
    # async_register_services(hass)

    api_info: CameServerInfo = api.server_info

    # add bridge device to device registry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(api.mac_address))},
        identifiers={
            (DOMAIN, api_info.keycode),
            (DOMAIN, api_info.serial),
        },
        manufacturer=MANUFACTURER,
        name=DEVICE_NAME,
        model=api_info.type,
        sw_version=api_info.swver,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_success = await hass.data[DOMAIN][entry.entry_id].async_reset()
    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)
        # hass.services.async_remove(DOMAIN, SERVICE_HUE_ACTIVATE_SCENE)
    return unload_success
