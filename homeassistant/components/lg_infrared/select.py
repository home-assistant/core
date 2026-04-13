from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_INFRARED_ENTITY_ID, CONF_REGION, REGION_JAPAN
from .entity import LgIrEntity
from .models import LGIRRemoteData
from infrared_protocols.codes.lg.tv import LGTVCodeJP

TUNER_COMMANDS: dict[str, LGTVCodeJP] = {
    "DTV": LGTVCodeJP.DTV,
    "BS": LGTVCodeJP.BS,
    "CS": LGTVCodeJP.CS,
}
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the LG IR select entities."""
    if entry.data.get(CONF_REGION) != REGION_JAPAN:
        return

    data: LGIRRemoteData = hass.data[DOMAIN][entry.entry_id]
    
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    async_add_entities([LGTVTunerSelect(data, entry, infrared_entity_id)])

class LGTVTunerSelect(LgIrEntity, SelectEntity):
    """Representation of the tuner selection for Japanese LG TVs."""

    _attr_options = ["DTV", "BS", "CS"]
    _attr_has_entity_name = True
    _attr_translation_key = "tuner_select"

    def __init__(self, data: LGIRRemoteData, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize the select entity."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix="tuner_select")
        self._data = data
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }
        
        # Link this UI entity back to the data object
        self._data.select_entity = self

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option from the shared state."""
        return self._data.current_tuner

    async def async_select_option(self, option: str) -> None:
        """Change the selected option and send the IR command."""
        option_upper = option.upper()
        self._data.update_tuner(option_upper)
        await self._send_command(TUNER_COMMANDS[option_upper])
        
