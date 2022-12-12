"""Initialise HomeAssistant buttons for Honeygain."""
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HoneygainData
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Button set up for HoneyGain."""
    honeygain_data: HoneygainData = hass.data[DOMAIN][entry.entry_id]
    buttons: list[ButtonEntity] = [HoneygainPotButton(hass, honeygain_data)]
    async_add_entities(buttons)


class HoneygainPotButton(ButtonEntity):
    """Generate buttons for Honeygain actions."""

    hass: HomeAssistant
    button_description: ButtonEntityDescription
    _honeygain_data: HoneygainData

    def __init__(self, hass: HomeAssistant, honeygain_data: HoneygainData) -> None:
        """Initialise a button."""
        self.hass = hass
        self._honeygain_data = honeygain_data
        self.button_description = ButtonEntityDescription(
            key="open_lucky_pot",
            name="Open lucky pot",
            icon="mdi:gift-open",
        )
        self.entity_id = f"button.{self.button_description.key}"
        self._attr_name = self.button_description.name
        self._attr_icon = self.button_description.icon
        self._attr_unique_id = f"honeygain-{self._honeygain_data.user['referral_code']}-{self.button_description.key}"

    def press(self) -> None:
        """Handle the button press."""
        self._honeygain_data.open_daily_pot()
        self._honeygain_data.update()
