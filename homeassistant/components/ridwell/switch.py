"""Support for Ridwell buttons."""

from __future__ import annotations

from typing import Any

from aioridwell.errors import RidwellError
from aioridwell.model import EventState, RidwellAccount

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RidwellDataUpdateCoordinator
from .entity import RidwellEntity

SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="opt_in",
    translation_key="opt_in",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ridwell sensors based on a config entry."""
    coordinator: RidwellDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        RidwellSwitch(coordinator, account, SWITCH_DESCRIPTION)
        for account in coordinator.accounts.values()
    )


class RidwellSwitch(RidwellEntity, SwitchEntity):
    """Define a Ridwell switch."""

    def __init__(
        self,
        coordinator: RidwellDataUpdateCoordinator,
        account: RidwellAccount,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, account)

        self._attr_unique_id = f"{account.account_id}_{description.key}"
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.next_pickup_event.state == EventState.SCHEDULED

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.next_pickup_event.async_opt_out()
        except RidwellError as err:
            raise HomeAssistantError(f"Error while opting out: {err}") from err

        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.next_pickup_event.async_opt_in()
        except RidwellError as err:
            raise HomeAssistantError(f"Error while opting in: {err}") from err

        await self.coordinator.async_request_refresh()
