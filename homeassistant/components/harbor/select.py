"""Select entities for Harbor."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast, override

from harbor import HarborCommandError
from harbor.mqtt import NIGHT_MODE_MODES, NightMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import HarborConfigEntry, HarborCoordinator
from .entity import HarborEntity

# Commands are sent over a single MQTT session to one camera, and each settings
# write is followed by a settings refresh, so they are serialized.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HarborSelectEntityDescription(SelectEntityDescription):
    """Describes a Harbor select entity."""

    select_fn: Callable[[HarborCoordinator, str], Coroutine[Any, Any, None]]


CAMERA_SELECTS: tuple[HarborSelectEntityDescription, ...] = (
    HarborSelectEntityDescription(
        key="night_mode_preference",
        translation_key="night_mode_preference",
        entity_category=EntityCategory.CONFIG,
        options=list(NIGHT_MODE_MODES),
        select_fn=lambda coordinator, option: coordinator.async_set_night_mode(
            cast(NightMode, option)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HarborConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Harbor selects from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        HarborSelect(coordinator, description) for description in CAMERA_SELECTS
    )


class HarborSelect(HarborEntity, SelectEntity):
    """A Harbor select entity."""

    entity_description: HarborSelectEntityDescription

    def __init__(
        self,
        coordinator: HarborCoordinator,
        description: HarborSelectEntityDescription,
    ) -> None:
        """Initialize the Harbor select."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @override
    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        option = self.coordinator.data.values.get(self.entity_description.key)
        # The library falls back to the literal string "unknown" for any value
        # it doesn't recognize.
        return option if option in self.options else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            await self.entity_description.select_fn(self.coordinator, option)
        except (HarborCommandError, TimeoutError, ConnectionError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="select_option_failed",
                translation_placeholders={
                    "option": option,
                    "select": self.entity_description.key,
                },
            ) from err
