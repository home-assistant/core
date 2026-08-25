"""Switch entities for Harbor."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from harbor import HarborCommandError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
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
class HarborSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Harbor switch entity."""

    turn_on_fn: Callable[[HarborCoordinator], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[HarborCoordinator], Coroutine[Any, Any, None]]


CAMERA_SWITCHES: tuple[HarborSwitchEntityDescription, ...] = (
    HarborSwitchEntityDescription(
        key="camera_on",
        translation_key="camera_on",
        turn_on_fn=lambda coordinator: coordinator.async_set_camera_on(True),
        turn_off_fn=lambda coordinator: coordinator.async_set_camera_on(False),
    ),
    HarborSwitchEntityDescription(
        key="video_flip",
        translation_key="video_flip",
        entity_category=EntityCategory.CONFIG,
        turn_on_fn=lambda coordinator: coordinator.async_set_video_flip(True),
        turn_off_fn=lambda coordinator: coordinator.async_set_video_flip(False),
    ),
    HarborSwitchEntityDescription(
        key="clock_display",
        translation_key="clock_display",
        entity_category=EntityCategory.CONFIG,
        turn_on_fn=lambda coordinator: coordinator.async_set_clock_display(True),
        turn_off_fn=lambda coordinator: coordinator.async_set_clock_display(False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HarborConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Harbor switches from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        HarborSwitch(coordinator, description) for description in CAMERA_SWITCHES
    )


class HarborSwitch(HarborEntity, SwitchEntity):
    """A Harbor switch entity."""

    entity_description: HarborSwitchEntityDescription

    def __init__(
        self,
        coordinator: HarborCoordinator,
        description: HarborSwitchEntityDescription,
    ) -> None:
        """Initialize the Harbor switch."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @override
    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self.coordinator.data.values.get(self.entity_description.key)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_call(self.entity_description.turn_on_fn, "turn_on")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_call(self.entity_description.turn_off_fn, "turn_off")

    async def _async_call(
        self,
        action: Callable[[HarborCoordinator], Coroutine[Any, Any, None]],
        translation_key: str,
    ) -> None:
        """Run a switch command and translate library errors."""
        try:
            await action(self.coordinator)
        except (HarborCommandError, TimeoutError, ConnectionError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=f"switch_{translation_key}_failed",
                translation_placeholders={"switch": self.entity_description.key},
            ) from err
