"""Button platform for LG IR integration."""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass

import logging
_LOGGER = logging.getLogger(__name__)

from infrared_protocols.codes.lg.tv import LGTVCode, LGTVCodeJP

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .codes import resolve_numeric_code
from .codesets import LG_CODESETS, LGCodeset, LgIrButtonEntityDescription
from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, LGDeviceType, CONF_CODESET, DOMAIN
from .entity import LgIrEntity
from .models import LGIRRemoteData

PARALLEL_UPDATES = 1

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG IR buttons from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    codeset_key = entry.data.get(CONF_CODESET)
    codeset_def = LG_CODESETS.get(codeset_key)

    if not codeset_def:
        _LOGGER.error("Unknown codeset: %s", codeset_key)
        return
        
    data: LGIRRemoteData = hass.data[DOMAIN][entry.entry_id]
       
    async_add_entities(
        LgIrButton(entry, infrared_entity_id, description, data, codeset_def)
            for description in codeset_def.buttons
    )


class LgIrButton(LgIrEntity, ButtonEntity):
    """LG IR button entity."""

    entity_description: LgIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: LgIrButtonEntityDescription,
        data: LGIRRemoteData,
        codeset_def: LGCodeset,
    ) -> None:
        """Initialize LG IR button."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix=description.key)
        self.entity_description = description
        self._data = data
        self._codeset_def = codeset_def

    async def async_press(self) -> None:
        """Press the button."""
        key = self.entity_description.key
        command = self.entity_description.command_code

        if self._codeset_def.tuner_options and key.upper() in self._codeset_def.tuner_options:
            self._data.update_tuner(key)
        elif key.startswith("num_"):
            tuner = self._data.current_tuner or "DTV"
            command = resolve_numeric_code(command, tuner)

        await self._send_command(command)
