"""LG IR tuner select entity (Japan only)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, CONF_INFRARED_ENTITY_ID, CONF_CODESET, tuner_signal
from .entity import LgIrEntity
from .models import LGIRRemoteData
from .codesets import LG_CODESETS, LGCodeset

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the LG IR select entities."""

    # Does codeset support tuner?
    codeset_key = entry.data.get(CONF_CODESET)
    codeset_def = LG_CODESETS.get(codeset_key)
    if not codeset_def or not codeset_def.has_tuner:
        return

    data: LGIRRemoteData = hass.data[DOMAIN][entry.entry_id]
    
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    async_add_entities([LGTVTunerSelect(data, entry, infrared_entity_id,codeset_def)])

class LGTVTunerSelect(LgIrEntity, SelectEntity):
    """Representation of the tuner selection for Japanese LG TVs."""

    _attr_has_entity_name = True
    _attr_translation_key = "tuner_select"

    def __init__(self, data: LGIRRemoteData, entry: ConfigEntry, infrared_entity_id: str, codeset_def: LGCodeset) -> None:
        """Initialize the select entity."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix="tuner_select")
        self._codeset_def = codeset_def
        self._data = data
        if codeset_def.tuner_options:
            self._attr_options = codeset_def.tuner_options
        else:
            self._attr_options = []
        self._entry_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option from the shared state."""
        return self._data.current_tuner

    async def async_select_option(self, option: str) -> None:
        command = getattr(self._codeset_def.codes, option.upper(), None)      
        if command:
            await self._send_command(command)
            self._data.update_tuner(option.upper()) # Sync state for numeric keys
        else:
            _LOGGER.warning("Tuner option %s has no corresponding IR code in %s", option, self._codeset_def.name)
    
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        # Connect to the tuner signal with automatic cleanup
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                tuner_signal(self._entry_id),
                self.async_write_ha_state,
            )
        )
        
