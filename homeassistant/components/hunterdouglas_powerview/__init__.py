"""The Hunter Douglas PowerView integration."""
import logging

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.helpers.api_base import ApiEntryPoint
from aiopvapi.helpers.tools import base64_to_unicode
from aiopvapi.rooms import Rooms
from aiopvapi.scenes import Scenes
from aiopvapi.shades import Shades
from aiopvapi.userdata import UserData
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    API_PATH_FWVERSION,
    DEFAULT_LEGACY_MAINPROCESSOR,
    DOMAIN,
    FIRMWARE,
    FIRMWARE_MAINPROCESSOR,
    FIRMWARE_NAME,
    HUB_EXCEPTIONS,
    HUB_NAME,
    MAC_ADDRESS_IN_USERDATA,
    ROOM_DATA,
    SCENE_DATA,
    SERIAL_NUMBER_IN_USERDATA,
    SHADE_DATA,
    USER_DATA,
)
from .coordinator import PowerviewShadeUpdateCoordinator
from .model import PowerviewDeviceInfo, PowerviewEntryData
from .shade_data import PowerviewShadeData
from .util import async_map_data_by_id

PARALLEL_UPDATES = 1

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [
    Platform.BUTTON,
    Platform.COVER,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hunter Douglas PowerView from a config entry."""

    config = entry.data

    hub_address = config[CONF_HOST]
    websession = async_get_clientsession(hass)

    pv_request = AioRequest(hub_address, loop=hass.loop, websession=websession)

    try:
        async with async_timeout.timeout(10):
            device_info = await async_get_device_info(pv_request, hub_address)

        async with async_timeout.timeout(10):
            rooms = Rooms(pv_request)
            room_data = async_map_data_by_id((await rooms.get_resources())[ROOM_DATA])

        async with async_timeout.timeout(10):
            scenes = Scenes(pv_request)
            scene_data = async_map_data_by_id(
                (await scenes.get_resources())[SCENE_DATA]
            )

        async with async_timeout.timeout(10):
            shades = Shades(pv_request)
            shade_entries = await shades.get_resources()
            shade_data = async_map_data_by_id(shade_entries[SHADE_DATA])

    except HUB_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            f"Connection error to PowerView hub: {hub_address}: {err}"
        ) from err
    if not device_info:
        raise ConfigEntryNotReady(f"Unable to initialize PowerView hub: {hub_address}")

    coordinator = PowerviewShadeUpdateCoordinator(hass, shades, hub_address)
    coordinator.async_set_updated_data(PowerviewShadeData())
    # populate raw shade data into the coordinator for diagnostics
    coordinator.data.store_group_data(shade_entries[SHADE_DATA])

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = PowerviewEntryData(
        api=pv_request,
        room_data=room_data,
        scene_data=scene_data,
        shade_data=shade_data,
        coordinator=coordinator,
        device_info=device_info,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_get_device_info(
    pv_request: AioRequest, hub_address: str
) -> PowerviewDeviceInfo:
    """Determine device info."""
    userdata = UserData(pv_request)
    resources = await userdata.get_resources()
    userdata_data = resources[USER_DATA]

    if FIRMWARE in userdata_data:
        main_processor_info = userdata_data[FIRMWARE][FIRMWARE_MAINPROCESSOR]
    elif userdata_data:
        # Legacy devices
        fwversion = ApiEntryPoint(pv_request, API_PATH_FWVERSION)
        resources = await fwversion.get_resources()

        if FIRMWARE in resources:
            main_processor_info = resources[FIRMWARE][FIRMWARE_MAINPROCESSOR]
        else:
            main_processor_info = DEFAULT_LEGACY_MAINPROCESSOR

    return PowerviewDeviceInfo(
        name=base64_to_unicode(userdata_data[HUB_NAME]),
        mac_address=userdata_data[MAC_ADDRESS_IN_USERDATA],
        serial_number=userdata_data[SERIAL_NUMBER_IN_USERDATA],
        firmware=main_processor_info,
        model=main_processor_info[FIRMWARE_NAME],
        hub_address=hub_address,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
