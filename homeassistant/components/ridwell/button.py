"""Support for Ridwell buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RidwellEntity
from .const import DATA_ACCOUNT, DATA_COORDINATOR, DOMAIN, LOGGER

BUTTON_OPT_IN = "opt_in"
BUTTON_OPT_OUT = "opt_out"

BUTTON_DESCRIPTIONS = (
    ButtonEntityDescription(
        key=BUTTON_OPT_IN,
        name="Opt In to Next Pickup",
    ),
    ButtonEntityDescription(
        key=BUTTON_OPT_OUT,
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
        LOGGER.error("HERE")
