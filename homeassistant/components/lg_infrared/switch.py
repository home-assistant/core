"""Switch platform for LG IR integration — LG AC toggles with discrete codes."""

from dataclasses import dataclass
from typing import Any, override

from infrared_protocols.codes.lg.ac import LgAcButton

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, LGDeviceType
from .entity import LgIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LgAcSwitchEntityDescription(SwitchEntityDescription):
    """Describes an LG AC switch backed by separate on and off IR codes."""

    on_code: LgAcButton
    off_code: LgAcButton


AC_SWITCH_DESCRIPTIONS: tuple[LgAcSwitchEntityDescription, ...] = (
    LgAcSwitchEntityDescription(
        key="ion_generator",
        translation_key="ion_generator",
        on_code=LgAcButton.ION_GENERATOR_ON,
        off_code=LgAcButton.ION_GENERATOR_OFF,
    ),
    LgAcSwitchEntityDescription(
        key="auto_clean",
        translation_key="auto_clean",
        on_code=LgAcButton.AUTO_CLEAN_ON,
        off_code=LgAcButton.AUTO_CLEAN_OFF,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG AC switches from a config entry."""
    if entry.data[CONF_DEVICE_TYPE] != LGDeviceType.AC:
        return

    emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    async_add_entities(
        LgAcSwitch(entry, emitter_entity_id, description)
        for description in AC_SWITCH_DESCRIPTIONS
    )


class LgAcSwitch(
    LgIrEntity, InfraredEmitterConsumerEntity, SwitchEntity, RestoreEntity
):
    """An LG AC feature toggled by two discrete infrared codes."""

    _attr_assumed_state = True
    entity_description: LgAcSwitchEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        emitter_entity_id: str,
        description: LgAcSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(entry, unique_id_suffix=description.key, device_name="LG AC")
        self._infrared_emitter_entity_id = emitter_entity_id
        self.entity_description = description
        self._attr_is_on = False

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state, as infrared cannot read it back from the AC."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            self._attr_is_on = last_state.state == STATE_ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the feature on."""
        await self._send_command(self.entity_description.on_code.to_command())
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the feature off."""
        await self._send_command(self.entity_description.off_code.to_command())
        self._attr_is_on = False
        self.async_write_ha_state()
