"""Support for RainMachine selects."""
from __future__ import annotations

from dataclasses import dataclass

from regenmaschine.errors import RainMachineError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIT_SYSTEM_IMPERIAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RainMachineData, RainMachineEntity
from .const import DATA_RESTRICTIONS_UNIVERSAL, DOMAIN
from .model import (
    RainMachineEntityDescription,
    RainMachineEntityDescriptionMixinDataKey,
)
from .util import key_exists


@dataclass
class RainMachineSelectDescription(
    SelectEntityDescription,
    RainMachineEntityDescription,
    RainMachineEntityDescriptionMixinDataKey,
):
    """Describe a generic RainMachine select."""


@dataclass
class FreezeProtectionSelectOption:
    """Define an option for a freeze selection select."""

    api_value: float
    imperial_label: str
    metric_label: str


@dataclass
class FreezeProtectionTemperatureMixin:
    """Define an entity description mixin to include an options list."""

    options: list[FreezeProtectionSelectOption]


@dataclass
class FreezeProtectionSelectDescription(
    RainMachineSelectDescription, FreezeProtectionTemperatureMixin
):
    """Describe a freeze protection temperature select."""


TYPE_FREEZE_PROTECTION_TEMPERATURE = "freeze_protection_temperature"

SELECT_DESCRIPTIONS = (
    FreezeProtectionSelectDescription(
        key=TYPE_FREEZE_PROTECTION_TEMPERATURE,
        name="Freeze protection temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        api_category=DATA_RESTRICTIONS_UNIVERSAL,
        data_key="freezeProtectTemp",
        options=[
            FreezeProtectionSelectOption(
                api_value=0.0,
                imperial_label="32°F",
                metric_label="0°C",
            ),
            FreezeProtectionSelectOption(
                api_value=2.0,
                imperial_label="35.6°F",
                metric_label="2°C",
            ),
            FreezeProtectionSelectOption(
                api_value=5.0,
                imperial_label="41°F",
                metric_label="5°C",
            ),
            FreezeProtectionSelectOption(
                api_value=10.0,
                imperial_label="50°F",
                metric_label="10°C",
            ),
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up RainMachine selects based on a config entry."""
    data: RainMachineData = hass.data[DOMAIN][entry.entry_id]

    entity_map = {
        TYPE_FREEZE_PROTECTION_TEMPERATURE: FreezeProtectionTemperatureSelect,
    }

    async_add_entities(
        entity_map[description.key](entry, data, description, hass.config.units.name)
        for description in SELECT_DESCRIPTIONS
        if (
            (coordinator := data.coordinators[description.api_category]) is not None
            and coordinator.data
            and key_exists(coordinator.data, description.data_key)
        )
    )


class FreezeProtectionTemperatureSelect(RainMachineEntity, SelectEntity):
    """Define a RainMachine select."""

    entity_description: FreezeProtectionSelectDescription

    def __init__(
        self,
        entry: ConfigEntry,
        data: RainMachineData,
        description: FreezeProtectionSelectDescription,
        unit_system: str,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data, description)

        self._api_value_to_label_map = {}
        self._label_to_api_value_map = {}

        for option in description.options:
            if unit_system == CONF_UNIT_SYSTEM_IMPERIAL:
                label = option.imperial_label
            else:
                label = option.metric_label
            self._api_value_to_label_map[option.api_value] = label
            self._label_to_api_value_map[label] = option.api_value

        self._attr_options = list(self._label_to_api_value_map)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            await self._data.controller.restrictions.set_universal(
                {self.entity_description.data_key: self._label_to_api_value_map[option]}
            )
        except RainMachineError as err:
            raise HomeAssistantError(f"Error while setting {self.name}: {err}") from err

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity when new data is received."""
        raw_value = self.coordinator.data[self.entity_description.data_key]
        self._attr_current_option = self._api_value_to_label_map[raw_value]
