import logging
import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, API_URL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Redgtech from a config entry."""
    try:
        # Armazenar dados de configuração
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = {
            "config": entry.data,
            "light_entities": [],
            "switch_entities": []
        }

        # Inicializar listas para armazenar as entidades "light" e "switch"
        light_entities = []
        switch_entities = []

        # Buscar dados da API
        access_token = entry.data.get("access_token")
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{API_URL}/home_assistant?access_token={access_token}') as response:
                if response.status == 200:
                    data = await response.json()
                    _LOGGER.debug("Data received: %s", data)

                    # Filtrar itens que contêm "dim" no endpointId para luzes
                    for item in data.get("boards", []):
                        endpoint_id = item.get('endpointId', '')
                        value = item.get("value", False)
                        state = "on" if value else "off"
                        brightness = item.get("bright", 0)
                        
                        if 'dim' in endpoint_id.lower():
                            light_entities.append({
                                "id": endpoint_id,
                                "name": item.get("name", f"Light {endpoint_id}"),
                                "state": state,
                                "brightness": brightness
                            })
                        else:
                            switch_entities.append({
                                "id": endpoint_id,
                                "name": item.get("name", f"Switch {endpoint_id}"),
                                "state": state
                            })
        
        # Registrar as plataformas e adicionar as entidades "light" e "switch"
        hass.data[DOMAIN][entry.entry_id]["light_entities"] = light_entities
        hass.data[DOMAIN][entry.entry_id]["switch_entities"] = switch_entities
        if light_entities:
            await hass.config_entries.async_forward_entry_setups(entry, ["light"])
        if switch_entities:
            await hass.config_entries.async_forward_entry_setups(entry, ["switch"])

        _LOGGER.info("Redgtech setup completed.")
        return True

    except Exception as e:
        _LOGGER.error("Error during setup of Redgtech: %s", e)
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        await hass.config_entries.async_forward_entry_unload(entry, "light")
        await hass.config_entries.async_forward_entry_unload(entry, "switch")
        hass.data[DOMAIN].pop(entry.entry_id)
    return True