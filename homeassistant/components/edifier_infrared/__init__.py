"""Edifier infrared integration for Home Assistant."""

from infrared_protocols.codes.edifier.models import MODEL_TO_COMMAND_SET, EdifierModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_COMMAND_SET, CONF_INFRARED_ENTITY_ID

PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Edifier IR from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version > 2:
        return False

    if entry.version == 1:
        data = {**entry.data}
        # The R1700BT model was renamed to R1700BT (pre-2017), and its
        # command set was split from the one shared with the R1700BTs
        # family, which it was incorrectly grouped with.
        if data[CONF_MODEL] == "R1700BT":
            data[CONF_MODEL] = EdifierModel.R1700BT_PRE_2017.value
        command_set = MODEL_TO_COMMAND_SET[EdifierModel(data[CONF_MODEL])]
        data[CONF_COMMAND_SET] = command_set.value
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            unique_id=f"{command_set.value}_{data[CONF_INFRARED_ENTITY_ID]}",
            version=2,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Edifier IR config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
