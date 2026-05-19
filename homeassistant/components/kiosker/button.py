"""Button platform for Kiosker."""

from collections.abc import Callable
from dataclasses import dataclass

from kiosker import KioskerAPI

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KioskerConfigEntry
from .entity import KioskerEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class KioskerButtonEntityDescription(ButtonEntityDescription):
    """Describe a Kiosker button."""

    action_fn: Callable[[KioskerAPI], None] | None = None


BUTTONS: tuple[KioskerButtonEntityDescription, ...] = (
    KioskerButtonEntityDescription(
        key="ping",
        translation_key="ping",
        entity_category=EntityCategory.DIAGNOSTIC,
        action_fn=lambda api: api.ping(),
    ),
    KioskerButtonEntityDescription(
        key="navigateRefresh",
        translation_key="navigate_refresh",
        action_fn=lambda api: api.navigate_refresh(),
    ),
    KioskerButtonEntityDescription(
        key="navigateHome",
        translation_key="navigate_home",
        action_fn=lambda api: api.navigate_home(),
    ),
    KioskerButtonEntityDescription(
        key="navigateForward",
        translation_key="navigate_forward",
        action_fn=lambda api: api.navigate_forward(),
    ),
    KioskerButtonEntityDescription(
        key="navigateBackward",
        translation_key="navigate_backward",
        action_fn=lambda api: api.navigate_backward(),
    ),
    KioskerButtonEntityDescription(
        key="print",
        translation_key="print",
        action_fn=lambda api: api.print(),
    ),
    KioskerButtonEntityDescription(
        key="clearCache",
        translation_key="clear_cache",
        entity_category=EntityCategory.CONFIG,
        action_fn=lambda api: api.clear_cache(),
    ),
    KioskerButtonEntityDescription(
        key="clearCookies",
        translation_key="clear_cookies",
        entity_category=EntityCategory.CONFIG,
        action_fn=lambda api: api.clear_cookies(),
    ),
    KioskerButtonEntityDescription(
        key="screensaverInteract",
        translation_key="screensaver_interact",
        action_fn=lambda api: api.screensaver_interact(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KioskerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kiosker buttons based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        KioskerButton(coordinator, description) for description in BUTTONS
    )


class KioskerButton(KioskerEntity, ButtonEntity):
    """Representation of a Kiosker button."""

    entity_description: KioskerButtonEntityDescription

    async def async_press(self) -> None:
        """Handle button press."""
        if action_fn := self.entity_description.action_fn:
            await self.hass.async_add_executor_job(action_fn, self.coordinator.api)
