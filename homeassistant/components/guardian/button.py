"""Buttons for the Elexa Guardian integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from aioguardian import Client
from aioguardian.errors import GuardianError

from . import GuardianEntity
from .const import DATA_CLIENT, DOMAIN

BUTTON_TYPE_REBOOT = "reboot"
BUTTON_TYPE_RESET_VALVE_DIAGNOSTICS = "reset_valve_diagnostics"

BUTTON_DESCRIPTIONS = (
    EntityDescription(
        key=BUTTON_TYPE_REBOOT,
        name="Reboot",
    ),
    EntityDescription(
        key=BUTTON_TYPE_RESET_VALVE_DIAGNOSTICS,
        name="Reset valve diagnostics",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WLED button based on a config entry."""
    async_add_entities(
        [
            GuardianButton(
                entry,
                description,
                hass.data[DOMAIN][entry.entry_id][DATA_CLIENT],
            )
            for description in BUTTON_DESCRIPTIONS
        ]
    )


class GuardianButton(GuardianEntity, ButtonEntity):
    """Define a Guardian button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry: ConfigEntry,
        description: EntityDescription,
        client: Client,
    ) -> None:
        """Initialize."""
        super().__init__(entry, description)

        self._client = client

    async def async_press(self) -> None:
        """Send out a restart command."""
        if self.entity_description.key == BUTTON_TYPE_REBOOT:
            func = self._client.system.reboot
        else:
            func = self._client.valve.reset

        try:
            async with self._client:
                await func()
        except GuardianError as err:
            raise HomeAssistantError(
                f'Error while pressing button "{self.entity_description.key}": {err}'
            ) from err
