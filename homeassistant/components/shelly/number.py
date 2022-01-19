"""Number for Shelly."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Final, cast

import async_timeout

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AIOSHELLY_DEVICE_TIMEOUT_SEC, CONF_SLEEP_PERIOD
from .entity import (
    NumberAttributeDescription,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_attribute_entities,
)
from .utils import get_device_entry_gen

_LOGGER: Final = logging.getLogger(__name__)


NUMBERS: Final = {
    ("device", "valvePos"): NumberAttributeDescription(
        icon="mdi:pipe-valve",
        name="Valve Position",
        unit=PERCENTAGE,
        available=lambda block: cast(int, block.valveError) != 1,
        entity_category=EntityCategory.CONFIG,
        min=0,
        max=100,
        step=1,
        mode=NumberMode("slider"),
        rest_path="thermostat/0",
        rest_arg="pos",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers for device."""
    if get_device_entry_gen(config_entry) == 2:
        return

    if config_entry.data[CONF_SLEEP_PERIOD]:
        await async_setup_entry_attribute_entities(
            hass, config_entry, async_add_entities, NUMBERS, BlockSleepingNumber
        )


class BlockSleepingNumber(ShellySleepingBlockAttributeEntity, NumberEntity):
    """Represent a block sleeping number."""

    description: NumberAttributeDescription

    @property
    def value(self) -> float:
        """Return value of number."""
        if self.block is not None:
            return cast(float, self.attribute_value)

        return cast(float, self.last_state)

    @property
    def unit_of_measurement(self) -> str | None:
        """Return unit of number."""
        return cast(str, self._unit)

    @property
    def min_value(self) -> float:
        """Return minimum value."""
        return self.description.min

    @property
    def max_value(self) -> float:
        """Return maximum value."""
        return self.description.max

    @property
    def step(self) -> float:
        """Return step increment/decrement value."""
        return self.description.step

    @property
    def mode(self) -> NumberMode:
        """Return mode."""
        return self.description.mode

    async def async_set_value(self, value: float) -> None:
        """Set value."""
        # Example for Shelly Valve: http://192.168.188.187/thermostat/0?pos=13.0
        await self._set_state_full_path(
            self.description.rest_path, {self.description.rest_arg: value}
        )
        self.async_write_ha_state()

    async def _set_state_full_path(self, path: str, params: Any) -> Any:
        """Set block state (HTTP request)."""

        blocktype = self.unique_id.split("-")[-2]
        if blocktype != "device" and self.block:
            path = f"{path}/{self.block.channel}"

        _LOGGER.debug("Setting state for entity %s, state: %s", self.name, params)
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                return await self.wrapper.device.http_request("get", path, params)
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.error(
                "Setting state for entity %s failed, state: %s, error: %s",
                self.name,
                params,
                repr(err),
            )
