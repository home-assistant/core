"""Support for Ridwell buttons."""
from __future__ import annotations

from aioridwell.model import EventState, RidwellPickupEvent

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RidwellEntity
from .const import DATA_ACCOUNT, DATA_COORDINATOR, DOMAIN

BUTTON_TYPE_OPT_IN = "opt_in"
BUTTON_TYPE_OPT_OUT = "opt_out"

BUTTON_DESCRIPTIONS = (
    ButtonEntityDescription(
        key=BUTTON_TYPE_OPT_IN,
        name="Opt In to Next Pickup",
    ),
    ButtonEntityDescription(
        key=BUTTON_TYPE_OPT_OUT,
        name="Opt Out from Next Pickup",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ridwell sensors based on a config entry."""
    accounts = hass.data[DOMAIN][entry.entry_id][DATA_ACCOUNT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    async_add_entities(
        [
            RidwellButton(coordinator, account, description)
            for account in accounts.values()
            for description in BUTTON_DESCRIPTIONS
        ]
    )


class RidwellButton(RidwellEntity, ButtonEntity):
    """Define a Ridwell button."""

    async def async_press(self) -> None:
        """Press the button."""
        event: RidwellPickupEvent = self.coordinator.data[self._account.account_id]

        if self.entity_description.key == BUTTON_TYPE_OPT_IN:
            if event.state == EventState.SCHEDULED:
                raise ValueError(f"Already opted into {event.pickup_date} pickup")
            await event.async_opt_in()
        else:
            if event.state == EventState.SKIPPED:
                raise ValueError(f"Already opted out of {event.pickup_date} pickup")
            await event.async_opt_out()

        await self.coordinator.async_request_refresh()
