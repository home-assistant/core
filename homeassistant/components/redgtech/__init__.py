import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from .const import DOMAIN, API_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import aiohttp
from redgtech_api import RedgtechAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Redgtech from a config entry."""
    _LOGGER.debug("Setting up Redgtech entry: %s", entry.entry_id)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "entities": []
    }

    access_token = entry.data.get("access_token")
    if not access_token:
        _LOGGER.error("No access token found in config entry")
        return False

    session = async_get_clientsession(hass)
    try:
        async with session.get(f'{API_URL}/home_assistant?access_token={access_token}', timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            _LOGGER.debug("Received data from API: %s", data)

            entities = [
                {
                    "id": item.get('endpointId', ''),
                    "name": item.get("name", f"Entity {item.get('endpointId', '')}"),
                    "state": "on" if item.get("value", False) else "off",
                    "type": 'switch'
                }
                for item in data.get("boards", [])
            ]
            hass.data[DOMAIN][entry.entry_id]["entities"] = entities

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.debug("Successfully set up Redgtech entry: %s", entry.entry_id)
        return True

    except aiohttp.ClientResponseError as e:
        _LOGGER.error("HTTP error while setting up Redgtech entry: %s - Status: %s", e.message, e.status)
        return False
    except aiohttp.ClientError as e:
        _LOGGER.error("Client error while setting up Redgtech entry: %s", e)
        return False
    except Exception as e:
        _LOGGER.exception("Unexpected error setting up Redgtech entry: %s", entry.entry_id)
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Redgtech entry: %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)