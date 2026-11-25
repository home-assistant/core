"""Switch platform for Marantz IR integration.

Features with separate on and off IR codes are switches with an assumed state,
because infrared cannot read the state back from the amplifier.
"""

from dataclasses import dataclass
from typing import Any, override

from infrared_protocols.codes.marantz.audio import MarantzAudioCode

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import CONF_MODEL, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import MarantzIrConfigEntry
from .const import CONF_INFRARED_EMITTER_ENTITY_ID, MODELS
from .entity import MarantzIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MarantzIrSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Marantz IR switch backed by separate on and off codes."""

    on_code: MarantzAudioCode
    off_code: MarantzAudioCode


SWITCH_DESCRIPTIONS: tuple[MarantzIrSwitchEntityDescription, ...] = (
    MarantzIrSwitchEntityDescription(
        key="speaker_a",
        translation_key="speaker_a",
        on_code=MarantzAudioCode.SPEAKER_A_ON,
        off_code=MarantzAudioCode.SPEAKER_A_OFF,
    ),
    MarantzIrSwitchEntityDescription(
        key="speaker_b",
        translation_key="speaker_b",
        on_code=MarantzAudioCode.SPEAKER_B_ON,
        off_code=MarantzAudioCode.SPEAKER_B_OFF,
    ),
    MarantzIrSwitchEntityDescription(
        key="power_amp_direct",
        translation_key="power_amp_direct",
        on_code=MarantzAudioCode.POWER_AMP_DIRECT_ON,
        off_code=MarantzAudioCode.POWER_AMP_DIRECT_OFF,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarantzIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Marantz IR switches from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    model_codes = MODELS[entry.data[CONF_MODEL]].codes
    async_add_entities(
        MarantzIrSwitch(entry, infrared_entity_id, description)
        for description in SWITCH_DESCRIPTIONS
        if description.on_code in model_codes and description.off_code in model_codes
    )


class MarantzIrSwitch(MarantzIrEntity, SwitchEntity, RestoreEntity):
    """Marantz IR switch entity."""

    _attr_assumed_state = True
    entity_description: MarantzIrSwitchEntityDescription

    def __init__(
        self,
        entry: MarantzIrConfigEntry,
        infrared_entity_id: str,
        description: MarantzIrSwitchEntityDescription,
    ) -> None:
        """Initialize Marantz IR switch."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix=description.key)
        self.entity_description = description

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None and (
            last_state.state in (STATE_ON, STATE_OFF)
        ):
            self._attr_is_on = last_state.state == STATE_ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the on command."""
        await self._send_marantz_command(self.entity_description.on_code)
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the off command."""
        await self._send_marantz_command(self.entity_description.off_code)
        self._attr_is_on = False
        self.async_write_ha_state()
