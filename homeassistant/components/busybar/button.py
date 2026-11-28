"""Key press buttons for BUSY Bar."""

from dataclasses import dataclass
from typing import override

from busylib.exceptions import BusyBarError
from busylib.types import InputKey

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import BusyConfigEntry
from .entity import BusyEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BusyButtonEntityDescription(ButtonEntityDescription):
    """Describe a BUSY Bar key press button."""

    input_key: InputKey


BUTTONS = (
    BusyButtonEntityDescription(
        key="busy", translation_key="busy", input_key=InputKey.BUSY
    ),
    BusyButtonEntityDescription(
        key="start", translation_key="start", input_key=InputKey.START
    ),
    BusyButtonEntityDescription(
        key="off", translation_key="off", input_key=InputKey.OFF
    ),
    BusyButtonEntityDescription(
        key="custom",
        translation_key="custom",
        input_key=InputKey.CUSTOM,
        entity_registry_enabled_default=False,
    ),
    BusyButtonEntityDescription(
        key="up",
        translation_key="up",
        input_key=InputKey.UP,
        entity_registry_enabled_default=False,
    ),
    BusyButtonEntityDescription(
        key="down",
        translation_key="down",
        input_key=InputKey.DOWN,
        entity_registry_enabled_default=False,
    ),
    BusyButtonEntityDescription(
        key="ok",
        translation_key="ok",
        input_key=InputKey.OK,
        entity_registry_enabled_default=False,
    ),
    BusyButtonEntityDescription(
        key="back",
        translation_key="back",
        input_key=InputKey.BACK,
        entity_registry_enabled_default=False,
    ),
    BusyButtonEntityDescription(
        key="apps",
        translation_key="apps",
        input_key=InputKey.APPS,
        entity_registry_enabled_default=False,
    ),
    BusyButtonEntityDescription(
        key="settings",
        translation_key="settings",
        input_key=InputKey.SETTINGS,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BusyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BUSY Bar buttons."""
    async_add_entities(
        BusyButton(entry.runtime_data, description) for description in BUTTONS
    )


class BusyButton(BusyEntity, ButtonEntity):
    """Send a key press to the bar."""

    entity_description: BusyButtonEntityDescription

    @override
    async def async_press(self) -> None:
        """Press the key."""
        try:
            await self.coordinator.client.input(self.entity_description.input_key)
        except BusyBarError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="input_failed"
            ) from err
