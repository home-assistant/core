"""Select platform for LG IR integration — LG AC energy-limit cap."""

from typing import override

from infrared_protocols.codes.lg.ac import LgAcButton

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, LGDeviceType
from .entity import LgIrEntity

PARALLEL_UPDATES = 1

ENERGY_LIMIT_OFF = "off"

# The unit caps its power draw at the selected percentage; "off" removes the cap.
_ENERGY_LIMIT_TO_CODE: dict[str, LgAcButton] = {
    ENERGY_LIMIT_OFF: LgAcButton.ENERGY_LIMIT_OFF,
    "40": LgAcButton.ENERGY_LIMIT_40,
    "60": LgAcButton.ENERGY_LIMIT_60,
    "80": LgAcButton.ENERGY_LIMIT_80,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG AC energy-limit select from a config entry."""
    if entry.data[CONF_DEVICE_TYPE] != LGDeviceType.AC:
        return

    async_add_entities(
        [LgAcEnergyLimitSelect(entry, entry.data[CONF_INFRARED_ENTITY_ID])]
    )


class LgAcEnergyLimitSelect(
    LgIrEntity, InfraredEmitterConsumerEntity, SelectEntity, RestoreEntity
):
    """Selects the LG AC energy-consumption cap."""

    _attr_assumed_state = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "energy_limit"
    _attr_options = list(_ENERGY_LIMIT_TO_CODE)

    def __init__(self, entry: ConfigEntry, emitter_entity_id: str) -> None:
        """Initialize the energy-limit select."""
        super().__init__(entry, unique_id_suffix="energy_limit", device_name="LG AC")
        self._infrared_emitter_entity_id = emitter_entity_id
        self._attr_current_option = ENERGY_LIMIT_OFF

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state, as infrared cannot read it back from the AC."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if (
            last_state is not None
            and last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            and last_state.state in _ENERGY_LIMIT_TO_CODE
        ):
            self._attr_current_option = last_state.state

    @override
    async def async_select_option(self, option: str) -> None:
        """Send the code for the chosen energy cap."""
        await self._send_command(_ENERGY_LIMIT_TO_CODE[option].to_command())
        self._attr_current_option = option
        self.async_write_ha_state()
