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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GuardianData, ValveControllerEntity, ValveControllerEntityDescription
from .const import API_SYSTEM_DIAGNOSTICS, DOMAIN


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
        push_action=_async_reboot,
        device_class=ButtonDeviceClass.RESTART,
        # Buttons don't actually need a coordinator; we give them one so they can
        # properly inherit from GuardianEntity:
        api_category=API_SYSTEM_DIAGNOSTICS,
    ),
    ValveControllerButtonDescription(
        key=BUTTON_KIND_RESET_VALVE_DIAGNOSTICS,
        translation_key="reset_diagnostics",
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
    data: GuardianData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        GuardianButton(entry, data, description) for description in BUTTON_DESCRIPTIONS
    )


class GuardianButton(ValveControllerEntity, ButtonEntity):
    """Define a Guardian button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    entity_description: ValveControllerButtonDescription

    def __init__(
        self,
        entry: ConfigEntry,
        data: GuardianData,
        description: ValveControllerButtonDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data.valve_controller_coordinators, description)

        self._client = data.client

    async def async_press(self) -> None:
        """Send out a restart command."""
        try:
            async with self._client:
                await self.entity_description.push_action(self._client)
        except GuardianError as err:
            raise HomeAssistantError(
                f'Error while pressing button "{self.entity_id}": {err}'
            ) from err

        async_dispatcher_send(self.hass, self.coordinator.signal_reboot_requested)
