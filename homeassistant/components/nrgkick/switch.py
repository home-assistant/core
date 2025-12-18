"""Switch platform for NRGkick."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NRGkickConfigEntry, NRGkickDataUpdateCoordinator, NRGkickEntity
from .api import NRGkickApiClientError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick switches based on a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    entities: list[NRGkickSwitch] = [
        NRGkickSwitch(
            coordinator,
            key="charge_pause",
            value_path=["control", "charge_pause"],
        ),
    ]

    async_add_entities(entities)


class NRGkickSwitch(NRGkickEntity, SwitchEntity):
    """Representation of a NRGkick switch."""

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        *,
        key: str,
        value_path: list[str],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, key)
        self._value_path = value_path

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        data: Any = self.coordinator.data
        for key in self._value_path:
            if data is None:
                return None
            data = data.get(key)
        return bool(data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.async_set_charge_pause(True)
        except NRGkickApiClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={
                    "target": "charge_pause",
                    "value": "on",
                },
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.async_set_charge_pause(False)
        except NRGkickApiClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={
                    "target": "charge_pause",
                    "value": "off",
                },
            ) from err
