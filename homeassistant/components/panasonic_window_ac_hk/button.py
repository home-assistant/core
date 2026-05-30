"""Button platform for the Panasonic Window A/C (Hong Kong/Macau).

Quiet and Powerful are momentary toggles on the unit. They are sent as dedicated
short frames and carry no mode/temperature/fan/swing, so they are stateless
buttons rather than part of the climate entity.
"""

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PanasonicWindowAcHKConfigEntry
from .entity import PanasonicWindowAcHKEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PanasonicWindowAcHKButtonEntityDescription(ButtonEntityDescription):
    """Describes a Panasonic window A/C toggle button."""

    short_frame_kind: str


BUTTON_DESCRIPTIONS: tuple[PanasonicWindowAcHKButtonEntityDescription, ...] = (
    PanasonicWindowAcHKButtonEntityDescription(
        key="quiet", translation_key="quiet", short_frame_kind="quiet"
    ),
    PanasonicWindowAcHKButtonEntityDescription(
        key="powerful", translation_key="powerful", short_frame_kind="powerful"
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PanasonicWindowAcHKConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Quiet and Powerful buttons for one air conditioner."""
    async_add_entities(
        PanasonicWindowAcHKToggleButton(entry, description)
        for description in BUTTON_DESCRIPTIONS
    )


class PanasonicWindowAcHKToggleButton(PanasonicWindowAcHKEntity, ButtonEntity):
    """A momentary Quiet/Powerful toggle (short frame)."""

    entity_description: PanasonicWindowAcHKButtonEntityDescription

    def __init__(
        self,
        entry: PanasonicWindowAcHKConfigEntry,
        description: PanasonicWindowAcHKButtonEntityDescription,
    ) -> None:
        """Initialize the toggle button."""
        super().__init__(entry, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the Quiet/Powerful toggle frame."""
        await self._async_send_short(self.entity_description.short_frame_kind)
