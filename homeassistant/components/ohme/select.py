"""Platform for Ohme selects."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

from ohme import ApiException, ChargerMode, OhmeApiClient

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import OhmeConfigEntry
from .entity import OhmeEntity, OhmeEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OhmeSelectDescription(OhmeEntityDescription, SelectEntityDescription):
    """Class to describe an Ohme select entity."""

    select_fn: Callable[[OhmeApiClient, Any], Awaitable[None]]
    current_option_fn: Callable[[OhmeApiClient], str | None]


SELECT_DESCRIPTION: Final[OhmeSelectDescription] = OhmeSelectDescription(
    key="charge_mode",
    translation_key="charge_mode",
    select_fn=lambda client, mode: client.async_set_mode(mode),
    options=[e.value for e in ChargerMode],
    current_option_fn=lambda client: client.mode.value if client.mode else None,
    available_fn=lambda client: client.mode is not None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ohme selects."""
    coordinator = config_entry.runtime_data.charge_session_coordinator

    async_add_entities([OhmeSelect(coordinator, SELECT_DESCRIPTION)])


class OhmeSelect(OhmeEntity, SelectEntity):
    """Ohme select entity."""

    entity_description: OhmeSelectDescription

    async def async_select_option(self, option: str) -> None:
        """Handle the selection of an option."""
        try:
            await self.entity_description.select_fn(self.coordinator.client, option)
        except ApiException as e:
            raise HomeAssistantError(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e
        await self.coordinator.async_request_refresh()

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.entity_description.current_option_fn(self.coordinator.client)
