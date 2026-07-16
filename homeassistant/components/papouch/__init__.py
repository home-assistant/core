"""Initialization file of the integration."""

import logging

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
from .devices import PapouchDevice, Quido

_LOGGER = logging.getLogger(__name__)

DOMAIN = "papouch"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
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

    device = await create_device(api_client)

    if device is None:
        raise ConfigEntryNotReady(
            "Unsupported device or failed to identify device type"
        )

    coordinator = PapouchDataUpdateCoordinator(hass, api_client, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def create_device(api_client: PapouchApiClient) -> PapouchDevice:
    """Function that creates proper device instance."""

    info = await api_client.fetch_info()
    device = ET.fromstring(info).find("heartbeat").attrib.get("device")

    if "Quido" in device:
        device = device.split()
        number_inputs = device[2].split("/")[0]
        number_outputs = device[2].split("/")[1]
        return Quido(api_client, int(number_inputs), int(number_outputs))

    return None
