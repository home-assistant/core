"""Select platform for Qube Heat Pump."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import QubeConfigEntry
from .const import DOMAIN
from .coordinator import QubeCoordinator
from .entity import QubeEntity

PARALLEL_UPDATES = 1

SGREADY_A_KEY = "bms_sgready_a"
SGREADY_B_KEY = "bms_sgready_b"

SGREADY_MODE_OFF = "off"
SGREADY_MODE_BLOCK = "block"
SGREADY_MODE_PLUS = "plus"
SGREADY_MODE_MAX = "max"

SGREADY_OPTIONS = [
    SGREADY_MODE_OFF,
    SGREADY_MODE_BLOCK,
    SGREADY_MODE_PLUS,
    SGREADY_MODE_MAX,
]

SGREADY_MODE_TO_BITS: dict[str, tuple[bool, bool]] = {
    SGREADY_MODE_OFF: (False, False),
    SGREADY_MODE_BLOCK: (True, False),
    SGREADY_MODE_PLUS: (False, True),
    SGREADY_MODE_MAX: (True, True),
}

SGREADY_BITS_TO_MODE: dict[tuple[bool, bool], str] = {
    v: k for k, v in SGREADY_MODE_TO_BITS.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qube select entities."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([QubeSGReadySelect(coordinator, entry)])


class QubeSGReadySelect(QubeEntity, SelectEntity):
    """Qube SG Ready mode select entity."""

    _attr_options = SGREADY_OPTIONS
    _attr_translation_key = "sg_ready_mode"

    def __init__(
        self,
        coordinator: QubeCoordinator,
        entry: QubeConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}-sg_ready_mode"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and SGREADY_A_KEY in self.coordinator.data.switches
            and SGREADY_B_KEY in self.coordinator.data.switches
        )

    @property
    def current_option(self) -> str | None:
        """Return the current SG Ready mode."""
        bit_a = self.coordinator.data.switches.get(SGREADY_A_KEY)
        bit_b = self.coordinator.data.switches.get(SGREADY_B_KEY)
        if bit_a is None or bit_b is None:
            return None
        return SGREADY_BITS_TO_MODE.get((bool(bit_a), bool(bit_b)))

    async def async_select_option(self, option: str) -> None:
        """Set the SG Ready mode."""
        bits = SGREADY_MODE_TO_BITS[option]
        try:
            success_a = await self.coordinator.client.write_switch(
                SGREADY_A_KEY, bits[0]
            )
            success_b = await self.coordinator.client.write_switch(
                SGREADY_B_KEY, bits[1]
            )
        except (ConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_command_failed",
            ) from err
        if not success_a or not success_b:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_command_failed",
            )
        await self.coordinator.async_request_refresh()
