"""Support for the Nettigo Air Monitor service."""

import logging
from typing import override

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

from .const import DOMAIN
from .coordinator import NAMConfigEntry
from .entity import NAMEntity

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


class NAMButton(NAMEntity, ButtonEntity):
    """Define an Nettigo Air Monitor button."""

    @override
    async def async_press(self) -> None:
        """Triggers the restart."""
        try:
            await self.coordinator.nam.async_restart()
        except (ApiError, ClientError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_communication_action_error",
                translation_placeholders={
                    "entity": self.entity_id,
                    "device": self.coordinator.config_entry.title,
                },
            ) from err
        except AuthFailedError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={
                    "device": self.coordinator.config_entry.title,
                },
            ) from err
