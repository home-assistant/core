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

SG_READY_OPTIONS = ["off", "block", "plus", "max"]


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

    _attr_options = SG_READY_OPTIONS
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
        return super().available and self.coordinator.data.sg_ready_mode is not None

    @property
    def current_option(self) -> str | None:
        """Return the current SG Ready mode."""
        return self.coordinator.data.sg_ready_mode

    async def async_select_option(self, option: str) -> None:
        """Set the SG Ready mode."""
        try:
            success = await self.coordinator.client.set_sg_ready_mode(option)
        except (ConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_command_failed",
            ) from err
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_command_failed",
            )
        await self.coordinator.async_request_refresh()
