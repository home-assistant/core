"""Support for the Swedish weather institute weather service."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SMHI forecast as config entry."""

    # Setting unique id where missing
    if entry.unique_id is None:
        unique_id = f"{entry.data[CONF_LOCATION][CONF_LATITUDE]}-{entry.data[CONF_LOCATION][CONF_LONGITUDE]}"
        hass.config_entries.async_update_entry(entry, unique_id=unique_id)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version == 1:
        new_data = {
            CONF_NAME: entry.data[CONF_NAME],
            CONF_LOCATION: {
                CONF_LATITUDE: entry.data[CONF_LATITUDE],
                CONF_LONGITUDE: entry.data[CONF_LONGITUDE],
            },
        }
        new_unique_id = f"smhi-{entry.data[CONF_LATITUDE]}-{entry.data[CONF_LONGITUDE]}"

        if not hass.config_entries.async_update_entry(
            entry, data=new_data, unique_id=new_unique_id
        ):
            return False

        entry.version = 2
        new_unique_id_entity = f"smhi-{entry.data[CONF_LOCATION][CONF_LATITUDE]}-{entry.data[CONF_LOCATION][CONF_LONGITUDE]}"

        @callback
        def update_unique_id(entity_entry: RegistryEntry) -> dict[str, str]:
            """Update unique ID of entity entry."""
            return {"new_unique_id": new_unique_id_entity}

        await async_migrate_entries(hass, entry.entry_id, update_unique_id)

    return True
