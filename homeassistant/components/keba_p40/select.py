"""Select platform for KEBA P40 (phase mode)."""

from keba_kecontact_p40 import KebaP40Error

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import KebaP40ConfigEntry
from .entity import KebaP40Entity

PARALLEL_UPDATES = 1

OPTION_SINGLE = "single"
OPTION_THREE = "three"
PHASE_TO_OPTION = {1: OPTION_SINGLE, 3: OPTION_THREE}
OPTION_TO_PHASE = {OPTION_SINGLE: 1, OPTION_THREE: 3}

PHASE_SELECT = SelectEntityDescription(
    key="phases",
    translation_key="phases",
    entity_category=EntityCategory.CONFIG,
    options=[OPTION_SINGLE, OPTION_THREE],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaP40ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KEBA P40 phase select."""
    async_add_entities([KebaP40PhaseSelect(entry.runtime_data, PHASE_SELECT)])


class KebaP40PhaseSelect(KebaP40Entity, SelectEntity):
    """Select entity to switch between single- and three-phase charging."""

    @property
    def current_option(self) -> str | None:
        """Return the active phase mode."""
        return PHASE_TO_OPTION.get(self._wallbox.max_phases or 0)

    async def async_select_option(self, option: str) -> None:
        """Switch the phase mode."""
        try:
            await self.coordinator.client.set_phases(
                self.coordinator.serial, OPTION_TO_PHASE[option]
            )
        except KebaP40Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        await self.coordinator.async_request_refresh()
