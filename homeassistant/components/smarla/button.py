"""Support for the Swing2Sleep Smarla button entities."""

from dataclasses import dataclass

from pysmarlaapi.federwiege.services.classes import Property

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FederwiegeConfigEntry
from .entity import SmarlaBaseEntity, SmarlaEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SmarlaButtonEntityDescription(SmarlaEntityDescription, ButtonEntityDescription):
    """Class describing Swing2Sleep Smarla button entity."""


BUTTONS: list[SmarlaButtonEntityDescription] = [
    SmarlaButtonEntityDescription(
        key="send_diagnostics",
        translation_key="send_diagnostics",
        service="system",
        property="send_diagnostic_data",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FederwiegeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smarla buttons from config entry."""
    federwiege = config_entry.runtime_data
    async_add_entities(SmarlaButton(federwiege, desc) for desc in BUTTONS)


class SmarlaButton(SmarlaBaseEntity, ButtonEntity):
    """Representation of a Smarla button."""

    entity_description: SmarlaButtonEntityDescription

    _property: Property[str]

    def press(self) -> None:
        """Press the button."""
        self._property.set("Sent from Home Assistant")
