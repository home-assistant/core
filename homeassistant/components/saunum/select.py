"""Select platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry, LeilSaunaCoordinator
from .const import (
    REG_FAN_SPEED,
    REG_SAUNA_TYPE,
    SAUNA_TYPE_1,
    SAUNA_TYPE_2,
    SAUNA_TYPE_3,
)
from .entity import LeilSaunaEntity
from .helpers import get_custom_sauna_type_names

_LOGGER = logging.getLogger(__name__)

# Fan speed options mapping
FAN_SPEED_OPTIONS = {
    0: "off",
    1: "low",
    2: "medium",
    3: "high",
}

FAN_SPEED_REVERSE = {v: k for k, v in FAN_SPEED_OPTIONS.items()}

# Sauna type options mapping
SAUNA_TYPE_OPTIONS = {
    SAUNA_TYPE_1: "1",
    SAUNA_TYPE_2: "2",
    SAUNA_TYPE_3: "3",
}

SAUNA_TYPE_REVERSE = {v: k for k, v in SAUNA_TYPE_OPTIONS.items()}


@dataclass(frozen=True, kw_only=True)
class LeilSaunaSelectEntityDescription(SelectEntityDescription):
    """Describes Saunum Leil Sauna select entity."""

    register: int
    value_fn: Callable[[dict[str, Any]], int | None]
    options_map: dict[int, str]


SELECTS: tuple[LeilSaunaSelectEntityDescription, ...] = (
    LeilSaunaSelectEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        icon="mdi:fan",
        register=REG_FAN_SPEED,
        options=list(FAN_SPEED_OPTIONS.values()),
        value_fn=lambda data: data.get("fan_speed", 1),
        options_map=FAN_SPEED_OPTIONS,
    ),
    LeilSaunaSelectEntityDescription(
        key="sauna_type",
        translation_key="sauna_type",
        icon="mdi:format-list-bulleted-type",
        register=REG_SAUNA_TYPE,
        options=list(SAUNA_TYPE_OPTIONS.values()),
        value_fn=lambda data: data.get("sauna_type", -1),
        options_map=SAUNA_TYPE_OPTIONS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna select entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        LeilSaunaSelect(coordinator, description) for description in SELECTS
    )


class LeilSaunaSelect(LeilSaunaEntity, SelectEntity):
    """Representation of a Saunum Leil Sauna select entity."""

    entity_description: LeilSaunaSelectEntityDescription

    def __init__(
        self,
        coordinator: LeilSaunaCoordinator,
        description: LeilSaunaSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

        # Build instance-specific options for sauna type
        if self.entity_description.key == "sauna_type":
            if coordinator.config_entry is not None:
                custom_names = get_custom_sauna_type_names(coordinator.config_entry)
                # Use custom names directly as options (preserving casing)
                self._sauna_type_options: dict[int, str] | None = {
                    SAUNA_TYPE_1: custom_names[SAUNA_TYPE_1],
                    SAUNA_TYPE_2: custom_names[SAUNA_TYPE_2],
                    SAUNA_TYPE_3: custom_names[SAUNA_TYPE_3],
                }
                self._sauna_type_reverse: dict[str, int] | None = {
                    v: k for k, v in self._sauna_type_options.items()
                }
                self._attr_options = list(self._sauna_type_options.values())
            else:
                self._sauna_type_options = None
                self._sauna_type_reverse = None
        else:
            self._sauna_type_options = None
            self._sauna_type_reverse = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Subscribe to options updates for sauna type entity
        if (
            self.entity_description.key == "sauna_type"
            and self.coordinator.config_entry is not None
        ):
            self.async_on_remove(
                self.coordinator.config_entry.add_update_listener(
                    self._async_options_updated
                )
            )

    async def _async_options_updated(
        self, hass: HomeAssistant, entry: LeilSaunaConfigEntry
    ) -> None:
        """Handle options update."""
        if self.entity_description.key == "sauna_type":
            # Rebuild options with new custom names (preserving casing)
            custom_names = get_custom_sauna_type_names(entry)
            self._sauna_type_options = {
                SAUNA_TYPE_1: custom_names[SAUNA_TYPE_1],
                SAUNA_TYPE_2: custom_names[SAUNA_TYPE_2],
                SAUNA_TYPE_3: custom_names[SAUNA_TYPE_3],
            }
            self._sauna_type_reverse = {
                v: k for k, v in self._sauna_type_options.items()
            }
            self._attr_options = list(self._sauna_type_options.values())
            self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        value = self.entity_description.value_fn(self.coordinator.data)
        if value is not None:
            # Use instance-specific options for sauna type
            if self.entity_description.key == "sauna_type" and self._sauna_type_options:
                return self._sauna_type_options.get(value)
            if value in self.entity_description.options_map:
                return self.entity_description.options_map[value]
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        value = None

        # Determine which option mapping to use
        if self.entity_description.key == "fan_speed":
            if option in FAN_SPEED_REVERSE:
                value = FAN_SPEED_REVERSE[option]
        elif self.entity_description.key == "sauna_type":
            # Use instance-specific reverse mapping for sauna type
            if self._sauna_type_reverse and option in self._sauna_type_reverse:
                value = self._sauna_type_reverse[option]

        if value is not None:
            # Write the selected value to the register
            await self.coordinator.async_write_register(
                self.entity_description.register, value
            )
