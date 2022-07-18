"""Buttons for the Elexa Guardian integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aioguardian import Client
from aioguardian.errors import GuardianError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ValveControllerEntity, ValveControllerEntityDescription
from .const import API_SYSTEM_DIAGNOSTICS, DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from .util import GuardianDataUpdateCoordinator


@dataclass
class GuardianButtonEntityDescriptionMixin:
    """Define an mixin for button entities."""

    push_action: Callable[[Client], Awaitable]


@dataclass
class ValveControllerButtonDescription(
    ButtonEntityDescription,
    ValveControllerEntityDescription,
    GuardianButtonEntityDescriptionMixin,
):
    """Describe a Guardian valve controller button."""


BUTTON_KIND_REBOOT = "reboot"
BUTTON_KIND_RESET_VALVE_DIAGNOSTICS = "reset_valve_diagnostics"


async def _async_reboot(client: Client) -> None:
    """Reboot the Guardian."""
    await client.system.reboot()


async def _async_valve_reset(client: Client) -> None:
    """Reset the valve diagnostics on the Guardian."""
    await client.valve.reset()


BUTTON_DESCRIPTIONS = (
    ValveControllerButtonDescription(
        key=BUTTON_KIND_REBOOT,
        name="Reboot",
        push_action=_async_reboot,
        # Buttons don't actually need a coordinator; we give them one so they can
        # properly inherit from GuardianEntity:
        api_category=API_SYSTEM_DIAGNOSTICS,
    ),
    ValveControllerButtonDescription(
        key=BUTTON_KIND_RESET_VALVE_DIAGNOSTICS,
        name="Reset valve diagnostics",
        push_action=_async_valve_reset,
        # Buttons don't actually need a coordinator; we give them one so they can
        # properly inherit from GuardianEntity:
        api_category=API_SYSTEM_DIAGNOSTICS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Guardian buttons based on a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client = entry_data[DATA_CLIENT]
    valve_controller_coordinators = entry_data[DATA_COORDINATOR]

    async_add_entities(
        [
            GuardianButton(entry, valve_controller_coordinators, description, client)
            for description in BUTTON_DESCRIPTIONS
        ]
    )


class GuardianButton(ValveControllerEntity, ButtonEntity):
    """Define a Guardian button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    entity_description: ValveControllerButtonDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinators: dict[str, GuardianDataUpdateCoordinator],
        description: ValveControllerButtonDescription,
        client: Client,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinators, description)

        self._client = client

    async def async_press(self) -> None:
        """Send out a restart command."""
        try:
            async with self._client:
                await self.entity_description.push_action(self._client)
        except GuardianError as err:
            raise HomeAssistantError(
                f'Error while pressing button "{self.entity_id}": {err}'
            ) from err
