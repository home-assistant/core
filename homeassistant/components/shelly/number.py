"""Number for Shelly."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Final, cast

import async_timeout

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import AIOSHELLY_DEVICE_TIMEOUT_SEC, CONF_SLEEP_PERIOD, LOGGER
from .entity import (
    BlockEntityDescription,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_attribute_entities,
)
from .utils import get_device_entry_gen


@dataclass
class BlockNumberDescription(BlockEntityDescription, NumberEntityDescription):
    """Class to describe a BLOCK sensor."""

    mode: NumberMode = NumberMode("slider")
    rest_path: str = ""
    rest_arg: str = ""


NUMBERS: Final = {
    ("device", "valvePos"): BlockNumberDescription(
        key="device|valvepos",
        icon="mdi:pipe-valve",
        name="Valve Position",
        native_unit_of_measurement=PERCENTAGE,
        available=lambda block: cast(int, block.valveError) != 1,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode("slider"),
        rest_path="thermostat/0",
        rest_arg="pos",
    ),
}


def _build_block_description(entry: RegistryEntry) -> BlockNumberDescription:
    """Build description when restoring block attribute entities."""
    assert entry.capabilities
    return BlockNumberDescription(
        key="",
        name="",
        icon=entry.original_icon,
        native_unit_of_measurement=entry.unit_of_measurement,
        device_class=entry.original_device_class,
        native_min_value=cast(float, entry.capabilities.get("min")),
        native_max_value=cast(float, entry.capabilities.get("max")),
        native_step=cast(float, entry.capabilities.get("step")),
        mode=cast(NumberMode, entry.capabilities.get("mode")),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers for device."""
    if get_device_entry_gen(config_entry) == 2:
        return

    if config_entry.data[CONF_SLEEP_PERIOD]:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            NUMBERS,
            BlockSleepingNumber,
            _build_block_description,
        )


class BlockSleepingNumber(ShellySleepingBlockAttributeEntity, NumberEntity):
    """Represent a block sleeping number."""

    entity_description: BlockNumberDescription

    @property
    def native_value(self) -> float:
        """Return value of number."""
        if self.block is not None:
            return cast(float, self.attribute_value)

        return cast(float, self.last_state)

    async def async_set_native_value(self, value: float) -> None:
        """Set value."""
        # Example for Shelly Valve: http://192.168.188.187/thermostat/0?pos=13.0
        await self._set_state_full_path(
            self.entity_description.rest_path,
            {self.entity_description.rest_arg: value},
        )
        self.async_write_ha_state()

    async def _set_state_full_path(self, path: str, params: Any) -> Any:
        """Set block state (HTTP request)."""

        LOGGER.debug("Setting state for entity %s, state: %s", self.name, params)
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                return await self.wrapper.device.http_request("get", path, params)
        except (asyncio.TimeoutError, OSError) as err:
            LOGGER.error(
                "Setting state for entity %s failed, state: %s, error: %s",
                self.name,
                params,
                repr(err),
            )
