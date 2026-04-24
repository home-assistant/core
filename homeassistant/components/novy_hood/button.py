"""Button platform for the Novy Hood.

Exposes one raw-command button per remote key, in addition to the fan and
light entities. These are categorised as config entities so they live in
the configuration section of the device page - useful for debugging the
RF link and for experimenting with the unknown `power` key.
"""

from __future__ import annotations

from rf_protocols import RadioFrequencyCommand

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .commands import NovyHoodLight, NovyHoodMinus, NovyHoodPlus, NovyHoodPower
from .entity import NovyHoodEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Novy Hood button platform."""
    async_add_entities(
        [
            NovyHoodCommandButton(config_entry, "plus", "Plus", NovyHoodPlus),
            NovyHoodCommandButton(config_entry, "minus", "Minus", NovyHoodMinus),
            NovyHoodCommandButton(config_entry, "light", "Light", NovyHoodLight),
            NovyHoodCommandButton(config_entry, "power", "Power", NovyHoodPower),
        ]
    )


class NovyHoodCommandButton(NovyHoodEntity, ButtonEntity):
    """Button that fires a single Novy hood RF command."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        key: str,
        name: str,
        command_cls: type[RadioFrequencyCommand],
    ) -> None:
        """Initialize the button."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._command_cls = command_cls

    async def async_press(self) -> None:
        """Send the RF command once."""
        await self._async_send(self._command_cls())
