"""Button platform for the SABnzbd component."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pysabnzbd import SabnzbdApiException

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SabnzbdConfigEntry, SabnzbdUpdateCoordinator
from .entity import SabnzbdEntity


@dataclass(kw_only=True, frozen=True)
class SabnzbdButtonEntityDescription(ButtonEntityDescription):
    """Describes SABnzbd button entity."""

    press_fn: Callable[[SabnzbdUpdateCoordinator], Any]


BUTTON_DESCRIPTIONS: tuple[SabnzbdButtonEntityDescription, ...] = (
    SabnzbdButtonEntityDescription(
        key="pause",
        translation_key="pause",
        press_fn=lambda coordinator: coordinator.sab_api.pause_queue(),
    ),
    SabnzbdButtonEntityDescription(
        key="resume",
        translation_key="resume",
        press_fn=lambda coordinator: coordinator.sab_api.resume_queue(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SabnzbdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        SabnzbdButton(coordinator, description) for description in BUTTON_DESCRIPTIONS
    )


class SabnzbdButton(SabnzbdEntity, ButtonEntity):
    """Representation of a SABnzbd button."""

    entity_description: SabnzbdButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.entity_description.press_fn(self.coordinator)
        except SabnzbdApiException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            await self.coordinator.async_request_refresh()
