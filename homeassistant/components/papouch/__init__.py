"""Initialization file of the integration."""

import aiohttp
import defusedxml.ElementTree as ET

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .APIClient import PapouchApiClient
from .coordinator import PapouchDataUpdateCoordinator
from .devices import TH2E, PapouchDevice, Quido

DOMAIN = "papouch"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type PapouchConfigEntry = ConfigEntry[PapouchDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup (unused)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PapouchConfigEntry) -> bool:
    """Set up Papouch device from a config entry."""

    session = async_get_clientsession(hass)
    api_client = PapouchApiClient(entry.data["ip_address"], session)

    try:
        device = await create_device(api_client)
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to Papouch device: {err}"
        ) from err

    if device is None:
        raise ConfigEntryNotReady(
            "Unsupported device or failed to identify device type"
        )

    coordinator = PapouchDataUpdateCoordinator(hass, api_client, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PapouchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def create_device(api_client: PapouchApiClient) -> PapouchDevice | None:
    """Function that creates proper device instance.

    Returns "None" if the device is not supported
    or when the device doesn't have proper identification tag.
    """

    info = await api_client.fetch_info()

    try:
        root = ET.fromstring(info)
        heartbeat = root.find("heartbeat")

        if heartbeat is None:
            return None

        device = heartbeat.attrib.get("device")

    except ET.ParseError:
        return None
    except AttributeError:
        return None

    if "Quido" in device:
        # settings are being fetched now, because ctor isn't async
        settings = await api_client.fetch_settings()
        return Quido(api_client, settings, info)
    elif "TH2E" in device:
        return TH2E(api_client, info)
    else:
        return None
