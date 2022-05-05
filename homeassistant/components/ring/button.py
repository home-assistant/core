"""This component provides HA button support for Ring Chimes."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .entity import RingEntityMixin

_LOGGER = logging.getLogger(__name__)

BELL_ICON = "mdi:bell-ring"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the buttons for the Ring devices."""
    devices = hass.data[DOMAIN][config_entry.entry_id]["devices"]
    buttons = []

    # add one button for each test chime type (ding, motion)
    for device in devices["chimes"]:
        buttons.append(ChimeButton(config_entry.entry_id, device, "ding"))
        buttons.append(ChimeButton(config_entry.entry_id, device, "motion"))

    async_add_entities(buttons)


class BaseRingButton(RingEntityMixin, ButtonEntity):
    """Represents a Button for controlling an aspect of a ring device."""

    def __init__(self, config_entry_id, device, button_identifier, button_name):
        """Initialize the switch."""
        super().__init__(config_entry_id, device)
        self._button_identifier = button_identifier
        self._button_name = button_name
        self._attr_unique_id = f"{self._device.id}-{self._button_identifier}"

    @property
    def name(self):
        """Name of the device."""
        return f"{self._device.name} {self._button_name}"


class ChimeButton(BaseRingButton):
    """Creates a button to play the test chime of a Chime device."""

    _attr_icon = BELL_ICON

    def __init__(self, config_entry_id, device, kind):
        """Initialize the button for a device with a chime."""
        super().__init__(
            config_entry_id, device, f"play-chime-{kind}", f"Play chime: {kind}"
        )
        self.kind = kind

    def press(self) -> None:
        """Send the test chime request."""
        if not self._device.test_sound(kind=self.kind):
            _LOGGER.error("Failed to ring chime sound on %s", self.name)
