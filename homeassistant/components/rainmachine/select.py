"""Support for RainMachine selects."""
from __future__ import annotations

from dataclasses import dataclass

from regenmaschine.errors import RainMachineError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RainMachineData, RainMachineEntity
from .const import DATA_RESTRICTIONS_UNIVERSAL, DOMAIN, LOGGER
from .model import (
    RainMachineEntityDescription,
    RainMachineEntityDescriptionMixinDataKey,
)
from .util import key_exists


@dataclass
class RainMachineEntityDescriptionMixinOptions:
    """Define an entity description mixin to include an options list."""

    options: list[str]


@dataclass
class RainMachineSelectDescription(
    SelectEntityDescription,
    RainMachineEntityDescription,
    RainMachineEntityDescriptionMixinDataKey,
    RainMachineEntityDescriptionMixinOptions,
):
    """Describe a RainMachine select."""


TYPE_FREEZE_PROTECTION_TEMPERATURE = "freeze_protection_temperature"

OPTION_FREEZE_PROTECTION_0 = "0°C/32°F"
OPTION_FREEZE_PROTECTION_2 = "2°C/35.6°F"
OPTION_FREEZE_PROTECTION_5 = "5°C/41°F"
OPTION_FREEZE_PROTECTION_10 = "10°C/50°F"

SELECT_DESCRIPTIONS = (
    RainMachineSelectDescription(
        key=TYPE_FREEZE_PROTECTION_TEMPERATURE,
        name="Freeze protect temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        api_category=DATA_RESTRICTIONS_UNIVERSAL,
        data_key="freezeProtectTemp",
        options=[
            OPTION_FREEZE_PROTECTION_0,
            OPTION_FREEZE_PROTECTION_2,
            OPTION_FREEZE_PROTECTION_5,
            OPTION_FREEZE_PROTECTION_10,
        ],
    ),
)

FREEZE_PROTECTION_RAW_VALUE_MAP = {
    OPTION_FREEZE_PROTECTION_0: 0.0,
    OPTION_FREEZE_PROTECTION_2: 2.0,
    OPTION_FREEZE_PROTECTION_5: 5.0,
    OPTION_FREEZE_PROTECTION_10: 10.0,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up RainMachine selects based on a config entry."""
    data: RainMachineData = hass.data[DOMAIN][entry.entry_id]

    api_category_select_map = {
        DATA_RESTRICTIONS_UNIVERSAL: UniversalRestrictionsSelect,
    }

    async_add_entities(
        [
            api_category_select_map[description.api_category](entry, data, description)
            for description in SELECT_DESCRIPTIONS
            if (
                (coordinator := data.coordinators[description.api_category]) is not None
                and coordinator.data
                and key_exists(coordinator.data, description.data_key)
            )
        ]
    )


class UniversalRestrictionsSelect(RainMachineEntity, SelectEntity):
    """Define a RainMachine select."""

    entity_description: RainMachineSelectDescription

    def __init__(
        self,
        entry: ConfigEntry,
        data: RainMachineData,
        description: RainMachineSelectDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data, description)

        self._attr_options = description.options

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        raw_value = FREEZE_PROTECTION_RAW_VALUE_MAP[option]

        try:
            await self._data.controller.restrictions.set_universal(
                {self.entity_description.data_key: raw_value}
            )
        except RainMachineError as err:
            LOGGER.error("Error while setting %s: %s", self.name, err)

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity when new data is received."""
        raw_value = self.coordinator.data[self.entity_description.data_key]

        try:
            [translated_value] = [
                k for k, v in FREEZE_PROTECTION_RAW_VALUE_MAP.items() if v == raw_value
            ]
        except ValueError:
            LOGGER.error("Cannot translate raw value: %s", raw_value)
            translated_value = None

        self._attr_current_option = translated_value
