"""Support for the Nettigo Air Monitor service."""

from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientError
from nettigo_air_monitor import ApiError, AuthFailedError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NAMConfigEntry, NAMDataUpdateCoordinator

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)

RESTART_BUTTON: ButtonEntityDescription = ButtonEntityDescription(
    key="restart",
    device_class=ButtonDeviceClass.RESTART,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NAMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a Nettigo Air Monitor entities from a config_entry."""
    coordinator = entry.runtime_data

    buttons: list[NAMButton] = []
    buttons.append(NAMButton(coordinator, RESTART_BUTTON))

    async_add_entities(buttons, False)


class NAMButton(CoordinatorEntity[NAMDataUpdateCoordinator], ButtonEntity):
    """Define an Nettigo Air Monitor button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NAMDataUpdateCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
        self.entity_description = description

    async def async_press(self) -> None:
        """Triggers the restart."""
        try:
            await self.coordinator.nam.async_restart()
        except (ApiError, ClientError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_communication_action_error",
                translation_placeholders={
                    "entity": self.entity_id,
                    "device": self.coordinator.config_entry.title,
                },
            ) from err
        except AuthFailedError:
            self.coordinator.config_entry.async_start_reauth(self.hass)
