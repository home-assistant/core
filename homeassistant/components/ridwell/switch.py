"""Support for Ridwell buttons."""
from __future__ import annotations

from typing import Any

from aioridwell.errors import RidwellError
from aioridwell.model import EventState, RidwellPickupEvent

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RidwellEntity
from .const import DATA_ACCOUNT, DATA_COORDINATOR, DOMAIN

SWITCH_TYPE_OPT_IN = "opt_in"

SWITCH_DESCRIPTION = SwitchEntityDescription(
    key=SWITCH_TYPE_OPT_IN,
    name="Opt-In to Next Pickup",
    icon="mdi:calendar-check",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ridwell sensors based on a config entry."""
    accounts = hass.data[DOMAIN][entry.entry_id][DATA_ACCOUNT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    async_add_entities(
        [
            RidwellSwitch(coordinator, account, SWITCH_DESCRIPTION)
            for account in accounts.values()
        ]
    )


class RidwellSwitch(RidwellEntity, SwitchEntity):
    """Define a Ridwell button."""

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        event: RidwellPickupEvent = self.coordinator.data[self._account.account_id]
        return event.state == EventState.SCHEDULED

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        event: RidwellPickupEvent = self.coordinator.data[self._account.account_id]

        try:
            await event.async_opt_out()
        except RidwellError as err:
            raise HomeAssistantError(f"Error while opting out: {err}") from err

        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        event: RidwellPickupEvent = self.coordinator.data[self._account.account_id]

        try:
            await event.async_opt_in()
        except RidwellError as err:
            raise HomeAssistantError(f"Error while opting in: {err}") from err

        await self.coordinator.async_request_refresh()
