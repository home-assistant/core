import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from .const import DOMAIN
from redgtech_api import RedgtechAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Redgtech from a config entry."""
    _LOGGER.debug("Setting up Redgtech entry: %s", entry.entry_id)
    
    entry.runtime_data = {
        "config": entry.data,
        "entities": []
    }

    access_token = entry.data.get("access_token")
    if not access_token:
        _LOGGER.error("No access token found in config entry")
        return False

    api = RedgtechAPI(access_token)
    try:
        data = await api.get_data()
        _LOGGER.debug("Received data from API: %s", data)

        entities = []
        for item in data.get("boards", []):
            entity_id = item.get('endpointId', '')
            entity_name = item.get("name", f"Entity {entity_id}")
            entity_value = item.get("value", False)
            entity_state = "on" if entity_value else "off"
            _LOGGER.debug("Processing entity: id=%s, name=%s, value=%s, state=%s", entity_id, entity_name, entity_value, entity_state)

            entities.append({
                "id": entity_id,
                "name": entity_name,
                "state": entity_state,
                "type": 'switch'
            })

        entry.runtime_data["entities"] = entities

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.debug("Successfully set up Redgtech entry: %s", entry.entry_id)
        return True

    except Exception as e:
        _LOGGER.error("Error setting up Redgtech entry: %s", e)
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Redgtech entry: %s", entry.entry_id)
    api = RedgtechAPI(entry.data.get("access_token"))
    await api.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)