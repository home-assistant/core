"""Switches for the Elexa Guardian integration."""
from __future__ import annotations

from typing import Any

from aioguardian import Client
from aioguardian.errors import GuardianError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import ValveControllerEntity
from .const import API_VALVE_STATUS, DATA_CLIENT, DATA_COORDINATOR, DOMAIN

ATTR_AVG_CURRENT = "average_current"
ATTR_INST_CURRENT = "instantaneous_current"
ATTR_INST_CURRENT_DDT = "instantaneous_current_ddt"
ATTR_TRAVEL_COUNT = "travel_count"

SWITCH_KIND_VALVE = "valve"

SWITCH_DESCRIPTION_VALVE = SwitchEntityDescription(
    key=SWITCH_KIND_VALVE,
    name="Valve Controller",
    icon="mdi:water",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Guardian switches based on a config entry."""
    async_add_entities(
        [
            ValveControllerSwitch(
                entry,
                hass.data[DOMAIN][entry.entry_id][DATA_CLIENT],
                hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR],
            )
        ]
    )


class ValveControllerSwitch(ValveControllerEntity, SwitchEntity):
    """Define a switch to open/close the Guardian valve."""

    def __init__(
        self,
        entry: ConfigEntry,
        client: Client,
        coordinators: dict[str, DataUpdateCoordinator],
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinators, SWITCH_DESCRIPTION_VALVE)

        self._attr_is_on = True
        self._client = client

    async def _async_continue_entity_setup(self) -> None:
        """Register API interest (and related tasks) when the entity is added."""
        self.async_add_coordinator_update_listener(API_VALVE_STATUS)

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        self._attr_available = self.coordinators[API_VALVE_STATUS].last_update_success
        self._attr_is_on = self.coordinators[API_VALVE_STATUS].data["state"] in (
            "start_opening",
            "opening",
            "finish_opening",
            "opened",
        )

        self._attr_extra_state_attributes.update(
            {
                ATTR_AVG_CURRENT: self.coordinators[API_VALVE_STATUS].data[
                    "average_current"
                ],
                ATTR_INST_CURRENT: self.coordinators[API_VALVE_STATUS].data[
                    "instantaneous_current"
                ],
                ATTR_INST_CURRENT_DDT: self.coordinators[API_VALVE_STATUS].data[
                    "instantaneous_current_ddt"
                ],
                ATTR_TRAVEL_COUNT: self.coordinators[API_VALVE_STATUS].data[
                    "travel_count"
                ],
            }
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the valve off (closed)."""
        try:
            async with self._client:
                await self._client.valve.close()
        except GuardianError as err:
            raise HomeAssistantError(f"Error while closing the valve: {err}") from err

        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the valve on (open)."""
        try:
            async with self._client:
                await self._client.valve.open()
        except GuardianError as err:
            raise HomeAssistantError(f"Error while opening the valve: {err}") from err

        self._attr_is_on = True
        self.async_write_ha_state()
